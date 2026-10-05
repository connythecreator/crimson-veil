//! Non-blocking WebSocket client to the Python control service.
//!
//! Uses `ewebsock` (egui's own client), polled from the UI thread each frame.
//! Reconnects with a capped backoff when the service is absent, so the kiosk
//! survives the backend starting late (or restarting).
//!
//! Binary frames (scan PNGs) are correlated with the preceding `scan_result`
//! header by arrival order: the server sends header-then-binary under a send
//! lock, so we stash the pending header and attach the next binary frame to it.

use std::time::{Duration, Instant};

use ewebsock::{Options, WsEvent, WsMessage, WsReceiver, WsSender};

use crate::protocol::{ClientMessage, ServerMessage};

const RECONNECT_MIN: Duration = Duration::from_millis(500);
const RECONNECT_MAX: Duration = Duration::from_secs(5);
const PING_EVERY: Duration = Duration::from_secs(10);

/// One message from the service, already decoded/correlated.
pub enum NetEvent {
    Connected,
    Disconnected,
    Server(ServerMessage),
    Image { id: String, width: u32, height: u32, png: Vec<u8> },
}

pub struct Net {
    url: String,
    sender: Option<WsSender>,
    receiver: Option<WsReceiver>,
    next_attempt: Instant,
    backoff: Duration,
    last_ping: Instant,
    pending_image: Option<(String, u32, u32)>,
}

impl Net {
    pub fn new(url: impl Into<String>) -> Self {
        let mut net = Self {
            url: url.into(),
            sender: None,
            receiver: None,
            next_attempt: Instant::now(),
            backoff: RECONNECT_MIN,
            last_ping: Instant::now(),
            pending_image: None,
        };
        net.connect();
        net
    }

    pub fn is_connected(&self) -> bool {
        self.sender.is_some()
    }

    fn connect(&mut self) {
        let (sender, receiver) = ewebsock::connect(self.url.clone(), Options::default())
            .expect("failed to spawn websocket client");
        self.sender = Some(sender);
        self.receiver = Some(receiver);
        // Greet so the service can re-announce `ready`.
        self.send(&ClientMessage::Hello {
            client: "kiosk-rs".into(),
            protocol: crate::protocol::PROTOCOL_VERSION,
        });
        self.last_ping = Instant::now();
    }

    pub fn send(&mut self, msg: &ClientMessage) {
        if let Some(sender) = &mut self.sender {
            sender.send(WsMessage::Text(msg.to_json()));
        }
    }

    /// Poll the socket; returns decoded events and reconnects as needed.
    pub fn poll(&mut self) -> Vec<NetEvent> {
        let mut out = Vec::new();
        let mut disconnected = false;

        if let Some(receiver) = &self.receiver {
            while let Some(event) = receiver.try_recv() {
                match event {
                    WsEvent::Opened => {
                        self.backoff = RECONNECT_MIN;
                        out.push(NetEvent::Connected);
                    }
                    WsEvent::Closed => disconnected = true,
                    WsEvent::Error(err) => {
                        log::warn!("websocket error: {err}");
                        disconnected = true;
                    }
                    WsEvent::Message(WsMessage::Text(text)) => {
                        match serde_json::from_str::<ServerMessage>(&text) {
                            Ok(msg) => {
                                if msg.kind == "scan_result" {
                                    self.pending_image = Some((msg.id.clone(), msg.width, msg.height));
                                }
                                out.push(NetEvent::Server(msg));
                            }
                            Err(err) => log::warn!("bad server message: {err}"),
                        }
                    }
                    WsEvent::Message(WsMessage::Binary(bytes)) => {
                        if let Some((id, width, height)) = self.pending_image.take() {
                            out.push(NetEvent::Image { id, width, height, png: bytes });
                        } else {
                            log::warn!("unexpected binary frame ({} bytes)", bytes.len());
                        }
                    }
                    WsEvent::Message(WsMessage::Ping(_) | WsMessage::Pong(_) | WsMessage::Unknown(_)) => {}
                }
            }
        }

        if disconnected {
            log::warn!("websocket closed; will reconnect");
            self.sender = None;
            self.receiver = None;
            self.pending_image = None;
            self.next_attempt = Instant::now() + self.backoff;
            self.backoff = (self.backoff * 2).min(RECONNECT_MAX);
            out.push(NetEvent::Disconnected);
        }

        if self.sender.is_none() && Instant::now() >= self.next_attempt {
            self.connect();
        }

        if self.is_connected() && self.last_ping.elapsed() >= PING_EVERY {
            self.send(&ClientMessage::Ping);
            self.last_ping = Instant::now();
        }

        out
    }
}
