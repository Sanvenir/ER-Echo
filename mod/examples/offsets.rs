//! 打印运行时结构偏移（只读研究用）：cargo run --example offsets
//!
//! 用途：给「外部只读探针」（tools/probe_face_memory.py）提供字段偏移。

use std::mem::{offset_of, size_of};

use eldenring::cs::{
    CSChrModelIns, CSFD4ModelItem, CSModelIns, ChrIns, PlayerGameData, PlayerIns, WorldChrMan,
};

fn main() {
    println!("size_of::<WorldChrMan>()       = 0x{:X}", size_of::<WorldChrMan>());
    println!("WorldChrMan.player_chr_set        = 0x{:X}", offset_of!(WorldChrMan, player_chr_set));
    println!("WorldChrMan.summon_buddy_chr_set  = 0x{:X}", offset_of!(WorldChrMan, summon_buddy_chr_set));
    println!("WorldChrMan.main_player           = 0x{:X}", offset_of!(WorldChrMan, main_player));

    println!("size_of::<PlayerIns>()            = 0x{:X}", size_of::<PlayerIns>());
    println!("PlayerIns.player_game_data        = 0x{:X}", offset_of!(PlayerIns, player_game_data));
    println!("PlayerIns.npc_param               = 0x{:X}", offset_of!(PlayerIns, npc_param));
    println!("PlayerIns.chr_asm                 = 0x{:X}", offset_of!(PlayerIns, chr_asm));

    println!("size_of::<ChrIns>()               = 0x{:X}", size_of::<ChrIns>());
    println!("ChrIns.chr_model_ins              = 0x{:X}", offset_of!(ChrIns, chr_model_ins));
    println!("ChrIns.chr_ctrl                   = 0x{:X}", offset_of!(ChrIns, chr_ctrl));
    println!("ChrIns.modules                    = 0x{:X}", offset_of!(ChrIns, modules));
    println!("ChrIns.npc_param_id               = 0x{:X}", offset_of!(ChrIns, npc_param_id));
    println!("ChrIns.team_type                  = 0x{:X}", offset_of!(ChrIns, team_type));

    println!("size_of::<CSChrModelIns>()        = 0x{:X}", size_of::<CSChrModelIns>());
    println!("size_of::<CSModelIns>()           = 0x{:X}", size_of::<CSModelIns>());
    println!("CSModelIns.model_item             = 0x{:X}", offset_of!(CSModelIns, model_item));
    println!("size_of::<CSFD4ModelItem>()       = 0x{:X}", size_of::<CSFD4ModelItem>());

    println!("size_of::<PlayerGameData>()       = 0x{:X}", size_of::<PlayerGameData>());
    println!("PlayerGameData.level              = 0x{:X}", offset_of!(PlayerGameData, level));
    println!("PlayerGameData.gender             = 0x{:X}", offset_of!(PlayerGameData, gender));
    println!("PlayerGameData.character_name     = 0x{:X}", offset_of!(PlayerGameData, character_name));
    println!("PlayerGameData.face_data          = 0x{:X}", offset_of!(PlayerGameData, face_data));

    println!("size_of::<FaceData>()             = 0x{:X}", size_of::<eldenring::cs::FaceData>());
    println!("size_of::<FaceDataBuffer>()       = 0x{:X}", size_of::<eldenring::cs::FaceDataBuffer>());
    println!("FaceDataBuffer.buffer             = 0x{:X}", offset_of!(eldenring::cs::FaceDataBuffer, buffer));
}
