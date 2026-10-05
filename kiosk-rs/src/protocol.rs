//! Wire protocol types for the Crimson Veil control surface.
//!
//! Mirrors `service/protocol.py`. Control messages are JSON text frames; a
//! `ScanResult` header is followed immediately by one binary frame holding the
//! PNG bytes. Keep the two sides in step.

use serde::{Deserialize, Serialize};

pub const PROTOCOL_VERSION: u32 = 1;

/// Messages the service sends to the kiosk. Unknown types are ignored by the
/// caller (forward compatibility): `type` is a plain string, not an enum.
#[derive(Debug, Clone, Deserialize)]
#[allow(dead_code)] // some fields are carried for completeness/future use
pub struct ServerMessage {
    #[serde(rename = "type")]
    pub kind: String,
    #[serde(default)]
    pub id: String,
    #[serde(default)]
    pub message: String,
    #[serde(default)]
    pub backend: String,
    #[serde(default)]
    pub solver: String,
    #[serde(default)]
    pub n_electrodes: u32,
    #[serde(default)]
    pub frequencies_hz: Vec<f64>,
    #[serde(default)]
    pub width: u32,
    #[serde(default)]
    pub height: u32,
    #[serde(default)]
    pub bytes: usize,
    #[serde(default)]
    pub continuous: bool,
    #[serde(default)]
    pub scanning: bool,
    #[serde(default)]
    pub battery_pct: Option<f32>,
    #[serde(default)]
    pub battery_charging: bool,
    #[serde(default)]
    pub temp_c: Option<f32>,
}

/// Messages the kiosk sends to the service.
#[derive(Debug, Clone, Serialize)]
#[serde(tag = "type")]
#[allow(dead_code)] // some variants are part of the protocol surface, used by future controls
pub enum ClientMessage {
    #[serde(rename = "hello")]
    Hello { client: String, protocol: u32 },
    #[serde(rename = "scan")]
    Scan { id: String },
    #[serde(rename = "continuous")]
    Continuous {
        on: bool,
        active_interval_s: f64,
        idle_interval_s: f64,
    },
    #[serde(rename = "activity")]
    Activity,
    #[serde(rename = "stop")]
    Stop,
    #[serde(rename = "set_freqs")]
    SetFreqs { frequencies_hz: Vec<f64> },
    #[serde(rename = "ping")]
    Ping,
}

impl ClientMessage {
    pub fn to_json(&self) -> String {
        serde_json::to_string(self).expect("client message is always serialisable")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_ready() {
        let raw = r#"{"type":"ready","backend":"sim:phantom","solver":"stub","n_electrodes":8,"frequencies_hz":[5000.0,20000.0]}"#;
        let m: ServerMessage = serde_json::from_str(raw).unwrap();
        assert_eq!(m.kind, "ready");
        assert_eq!(m.n_electrodes, 8);
        assert_eq!(m.frequencies_hz.len(), 2);
    }

    #[test]
    fn parse_scan_result() {
        let raw = r#"{"type":"scan_result","id":"abc","width":256,"height":256,"bytes":1234}"#;
        let m: ServerMessage = serde_json::from_str(raw).unwrap();
        assert_eq!(m.kind, "scan_result");
        assert_eq!(m.id, "abc");
        assert_eq!(m.width, 256);
        assert_eq!(m.bytes, 1234);
    }

    #[test]
    fn unknown_type_still_parses() {
        let m: ServerMessage = serde_json::from_str(r#"{"type":"something_new","x":1}"#).unwrap();
        assert_eq!(m.kind, "something_new");
    }

    #[test]
    fn encode_scan_request() {
        let json = ClientMessage::Scan { id: "s1".into() }.to_json();
        assert_eq!(json, r#"{"type":"scan","id":"s1"}"#);
    }

    #[test]
    fn encode_continuous() {
        let json = ClientMessage::Continuous {
            on: true,
            active_interval_s: 60.0,
            idle_interval_s: 120.0,
        }
        .to_json();
        assert!(json.contains(r#""type":"continuous""#));
        assert!(json.contains(r#""active_interval_s":60.0"#));
        assert!(json.contains(r#""idle_interval_s":120.0"#));
    }

    #[test]
    fn encode_activity() {
        let json = ClientMessage::Activity.to_json();
        assert_eq!(json, r#"{"type":"activity"}"#);
    }
}
