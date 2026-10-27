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
    pub frequency_hz: f64,
    #[serde(default)]
    pub baseline_ready: bool,
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
    pub on_battery: bool,
    #[serde(default)]
    pub battery_v: Option<f32>,
    #[serde(default)]
    pub runtime_s: Option<u32>,
    #[serde(default)]
    pub low_v: Option<f32>,
    #[serde(default)]
    pub temp_wittypi_c: Option<f32>,
    #[serde(default)]
    pub temp_esp32_c: Option<f32>,
    #[serde(default)]
    pub temp_ad5933_c: Option<f32>,
    #[serde(default)]
    pub temp_pi_c: Option<f32>,
    #[serde(default)]
    pub checks: Vec<Check>,
}

/// One line of the pre-start hardware self-test.
#[derive(Debug, Clone, Default, Deserialize)]
pub struct Check {
    #[serde(default)]
    pub name: String,
    /// pass | fail | warn | skip
    #[serde(default)]
    pub status: String,
    #[serde(default)]
    pub detail: String,
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
    #[serde(rename = "capture_baseline")]
    CaptureBaseline { id: String },
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
    #[serde(rename = "set_frequency")]
    SetFrequency { frequency_hz: f64 },
    #[serde(rename = "self_test")]
    SelfTest,
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
        let raw = r#"{"type":"ready","backend":"sim:phantom","solver":"stub","n_electrodes":8,"frequency_hz":50000.0}"#;
        let m: ServerMessage = serde_json::from_str(raw).unwrap();
        assert_eq!(m.kind, "ready");
        assert_eq!(m.n_electrodes, 8);
        assert_eq!(m.frequency_hz, 50000.0);
        assert!(!m.baseline_ready);
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

    #[test]
    fn encode_capture_baseline() {
        let json = ClientMessage::CaptureBaseline { id: "b1".into() }.to_json();
        assert_eq!(json, r#"{"type":"capture_baseline","id":"b1"}"#);
    }

    #[test]
    fn parse_baseline_metadata() {
        let ready: ServerMessage =
            serde_json::from_str(r#"{"type":"ready","baseline_ready":true}"#).unwrap();
        assert!(ready.baseline_ready);
        let captured: ServerMessage = serde_json::from_str(
            r#"{"type":"baseline_captured","id":"b1","frequency_hz":50000.0,"n_electrodes":8}"#,
        )
        .unwrap();
        assert_eq!(captured.kind, "baseline_captured");
        assert_eq!(captured.id, "b1");
    }

    #[test]
    fn encode_self_test() {
        assert_eq!(ClientMessage::SelfTest.to_json(), r#"{"type":"self_test"}"#);
    }

    #[test]
    fn parse_self_test_result() {
        let raw = r#"{"type":"self_test_result","checks":[{"name":"Battery","status":"pass","detail":"83% / 4.00 V"},{"name":"PyEIT","status":"fail","detail":"not installed"}]}"#;
        let m: ServerMessage = serde_json::from_str(raw).unwrap();
        assert_eq!(m.kind, "self_test_result");
        assert_eq!(m.checks.len(), 2);
        assert_eq!(m.checks[0].name, "Battery");
        assert_eq!(m.checks[0].status, "pass");
        assert_eq!(m.checks[1].status, "fail");
    }

    #[test]
    fn parse_metrics() {
        let raw = r#"{"type":"metrics","battery_pct":82.0,"battery_charging":false,"on_battery":true,"battery_v":3.86,"runtime_s":7200,"low_v":3.3,"temp_wittypi_c":31.5,"temp_esp32_c":52.0,"temp_ad5933_c":38.5,"temp_pi_c":44.0}"#;
        let m: ServerMessage = serde_json::from_str(raw).unwrap();
        assert_eq!(m.kind, "metrics");
        assert_eq!(m.battery_pct, Some(82.0));
        assert!(m.on_battery);
        assert_eq!(m.runtime_s, Some(7200));
        assert_eq!(m.temp_esp32_c, Some(52.0));
        assert_eq!(m.temp_pi_c, Some(44.0));
    }
}
