//! 与 Python sidecar 的 NDJSON/TCP 通道。
//!
//! - 游戏是 **client**（主动连 127.0.0.1:7811），sidecar 是 server。
//! - 收包在独立线程；游戏主线程只读原子/锁里的「最新权重」，永不阻塞。
//! - 断线自动重连；重连期间沿用 last-known-good 权重。

use std::io::{BufRead, BufReader, Write};
use std::net::TcpStream;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Mutex, OnceLock};
use std::time::Duration;

use serde::Deserialize;
use serde_json::Value;

use crate::params::Weights;

#[derive(Debug, Clone, Deserialize)]
pub struct Incoming {
    pub v: u32,
    #[serde(rename = "type")]
    pub kind: String,
    #[serde(default)]
    pub token: String,
    #[serde(default)]
    pub seq: u64,
    #[serde(default)]
    pub weights: Option<WeightsIn>,
    #[serde(default)]
    pub strategy: Option<String>,
    #[serde(default)]
    pub cmd: Option<String>,
    #[serde(default)]
    pub args: Option<Value>,
}

/// 一条 `weights` 消息里的权重。
///
/// 全部字段都是 `Option`：LLM 可以只发「这一轮想改的那几个」，没发的沿用上一轮。
/// （以前用 `f32` + `#[serde(default)]`，只发 `aggression` 会把其余 8 个静默清零 ——
/// 实测时 `spell_rate` 被清零、但克隆体照样施法，差点误判成「施法权重无效」。）
#[derive(Debug, Clone, Copy, Default, Deserialize)]
pub struct WeightsIn {
    #[serde(default)]
    pub aggression: Option<f32>,
    #[serde(default)]
    pub dodge_rate: Option<f32>,
    #[serde(default)]
    pub guard_rate: Option<f32>,
    #[serde(default)]
    pub combo_rate: Option<f32>,
    #[serde(default)]
    pub heal_priority: Option<f32>,
    #[serde(default)]
    pub spell_rate: Option<f32>,
    #[serde(default)]
    pub item_rate: Option<f32>,
    #[serde(default)]
    pub spacing: Option<f32>,
    #[serde(default)]
    pub target_switch: Option<f32>,
}

impl WeightsIn {
    /// 把「本轮给了的」叠在 `base` 上。
    pub fn merged(&self, base: &Weights) -> Weights {
        fn pick(v: Option<f32>, old: f32) -> f32 {
            v.map(|x| x.clamp(0.0, 1.0)).unwrap_or(old)
        }
        Weights {
            aggression: pick(self.aggression, base.aggression),
            dodge_rate: pick(self.dodge_rate, base.dodge_rate),
            guard_rate: pick(self.guard_rate, base.guard_rate),
            combo_rate: pick(self.combo_rate, base.combo_rate),
            heal_priority: pick(self.heal_priority, base.heal_priority),
            spell_rate: pick(self.spell_rate, base.spell_rate),
            item_rate: pick(self.item_rate, base.item_rate),
            spacing: pick(self.spacing, base.spacing),
            target_switch: pick(self.target_switch, base.target_switch),
        }
    }
}

pub struct Command {
    pub name: String,
    pub args: Value,
}

pub struct Mailbox {
    pub target: Mutex<Option<Weights>>,
    /// 上一轮生效的权重（部分字段更新时的基准）。
    pub last: Mutex<Weights>,
    pub seq: AtomicU64,
    pub strategy: Mutex<Option<String>>,
    pub commands: Mutex<Vec<Command>>,
    writer: Mutex<Option<TcpStream>>,
    pub connected: std::sync::atomic::AtomicBool,
}

static MAILBOX: OnceLock<Mailbox> = OnceLock::new();

pub fn mailbox() -> &'static Mailbox {
    MAILBOX.get_or_init(|| Mailbox {
        target: Mutex::new(None),
        last: Mutex::new(Weights {
            aggression: 0.5,
            dodge_rate: 0.5,
            guard_rate: 0.5,
            combo_rate: 0.5,
            heal_priority: 0.5,
            spell_rate: 0.5,
            item_rate: 0.5,
            spacing: 0.5,
            target_switch: 0.5,
        }),
        seq: AtomicU64::new(0),
        strategy: Mutex::new(None),
        commands: Mutex::new(Vec::new()),
        writer: Mutex::new(None),
        connected: std::sync::atomic::AtomicBool::new(false),
    })
}

/// 后台线程：连接 / 重连 / 收包。
pub fn start(addr: String, token: String) {
    std::thread::spawn(move || loop {
        match TcpStream::connect(&addr) {
            Ok(stream) => {
                stream.set_nodelay(true).ok();
                let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
                let mut writer = match stream.try_clone() {
                    Ok(w) => w,
                    Err(_) => continue,
                };
                if send_raw(&mut writer, &hello(&token)).is_err() {
                    continue;
                }
                if let Ok(mut guard) = mailbox().writer.lock() {
                    *guard = Some(writer);
                }
                mailbox().connected.store(true, Ordering::Release);
                log::info!("ipc connected to {addr}");

                let reader = BufReader::new(stream);
                // 注意：socket 设了 500ms 读超时，**超时不是断线**。
                // 以前用 `for line in reader.lines()`，超时会 yield Err 就 break → 连接每 500ms 断一次、
                // sidecar 2 秒后才重连，state 大量丢失（日志里成片的 ipc disconnected）。
                let mut lines = reader.lines();
                loop {
                    match lines.next() {
                        Some(Ok(line)) => {
                            if !line.trim().is_empty() {
                                handle_line(&line, &token);
                            }
                        }
                        Some(Err(err))
                            if matches!(
                                err.kind(),
                                std::io::ErrorKind::WouldBlock | std::io::ErrorKind::TimedOut
                            ) =>
                        {
                            continue;
                        }
                        Some(Err(_)) | None => break,
                    }
                }
                mailbox().connected.store(false, Ordering::Release);
                if let Ok(mut guard) = mailbox().writer.lock() {
                    *guard = None;
                }
                log::warn!("ipc disconnected");
            }
            Err(_) => {}
        }
        std::thread::sleep(Duration::from_secs(2));
    });
}

fn handle_line(line: &str, token: &str) {
    let Ok(msg) = serde_json::from_str::<Incoming>(line) else {
        return;
    };
    if msg.v != 1 || msg.token != token {
        log::warn!("ipc: bad envelope");
        return;
    }
    match msg.kind.as_str() {
        "hello" => {
            let pid = std::process::id();
            send_raw_global(&format!(
                "{{\"v\":1,\"type\":\"welcome\",\"token\":\"{token}\",\"pid\":{pid},\"version\":\"2.7.2.0\"}}\n"
            ));
        }
        "weights" => {
            if let Some(w) = msg.weights {
                // 部分字段更新：没给的沿用上一轮（见 `WeightsIn` 的注释）。
                let base = *mailbox().last.lock().unwrap_or_else(|e| e.into_inner());
                let merged = w.merged(&base);
                if let Ok(mut last) = mailbox().last.lock() {
                    *last = merged;
                }
                log::info!(
                    "ipc: weights seq={} aggr={:.2} dodge={:.2} guard={:.2} spell={:.2}",
                    msg.seq,
                    merged.aggression,
                    merged.dodge_rate,
                    merged.guard_rate,
                    merged.spell_rate
                );
                if let Ok(mut target) = mailbox().target.lock() {
                    *target = Some(merged);
                }
                mailbox().seq.store(msg.seq, Ordering::Release);
                if let Ok(mut s) = mailbox().strategy.lock() {
                    *s = msg.strategy;
                }
            }
        }
        "command" => {
            if let Some(name) = msg.cmd {
                log::info!("ipc: command {name}");
                if let Ok(mut q) = mailbox().commands.lock() {
                    if q.len() < 32 {
                        q.push(Command {
                            name,
                            args: msg.args.unwrap_or(Value::Null),
                        });
                    }
                }
            }
        }
        "ping" => send_raw_global(&format!("{{\"v\":1,\"type\":\"pong\",\"token\":\"{token}\"}}\n")),
        _ => {}
    }
}

/// 游戏主线程调用：发一条 state（非阻塞写；失败就丢）。
pub fn send_state(json: &str) {
    let line = format!("{json}\n");
    if let Ok(mut guard) = mailbox().writer.lock() {
        if let Some(stream) = guard.as_mut() {
            let _ = stream.write_all(line.as_bytes());
        }
    }
}

/// 命令回执。
pub fn send_ack(cmd: &str, ok: bool, detail: &str) {
    let detail = detail.replace('"', "'").replace('\n', " ");
    let line = format!(
        "{{\"v\":1,\"type\":\"ack\",\"cmd\":\"{cmd}\",\"ok\":{ok},\"detail\":\"{detail}\"}}\n"
    );
    send_raw_global(&line);
}

pub fn take_commands() -> Vec<Command> {
    mailbox()
        .commands
        .lock()
        .map(|mut q| std::mem::take(&mut *q))
        .unwrap_or_default()
}

pub fn is_connected() -> bool {
    mailbox().connected.load(Ordering::Acquire)
}

fn hello(token: &str) -> String {
    format!(
        "{{\"v\":1,\"type\":\"hello\",\"token\":\"{token}\",\"client\":\"er_echo.dll\",\"version\":\"0.1.0\"}}\n"
    )
}

fn send_raw(stream: &mut TcpStream, line: &str) -> std::io::Result<()> {
    stream.write_all(line.as_bytes())
}

fn send_raw_global(line: &str) {
    if let Ok(mut guard) = mailbox().writer.lock() {
        if let Some(stream) = guard.as_mut() {
            let _ = stream.write_all(line.as_bytes());
        }
    }
}
