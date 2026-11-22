# -*- coding: utf-8 -*-
def t000001000_1():
    """State 0,1"""
    t000001000_x22()
    Quit()

def t000001000_x0(action10=_):
    """State 0,1"""
    OpenGenericDialog(DialogBoxType.CenterBottom2, action10, DialogResult.Leave, DialogBoxStyle.Unk, 2)
    assert not CheckSpecificPersonGenericDialogIsOpen(0)
    """State 2"""
    if GetGenericDialogButtonResult() == DialogResult.Left:
        """State 3"""
        return 0
    else:
        """State 4"""
        return 1

def t000001000_x1():
    """State 0,1"""
    if not CheckSpecificPersonTalkHasEnded(0):
        """State 7"""
        ClearTalkProgressData()
        StopEventAnimWithoutForcingConversationEnd(0)
        """State 6"""
        ReportConversationEndToHavokBehavior()
    else:
        pass
    """State 2"""
    if CheckSpecificPersonGenericDialogIsOpen(0):
        """State 3"""
        ForceCloseGenericDialog()
    else:
        pass
    """State 4"""
    if CheckSpecificPersonMenuIsOpen(-1, 0) and not CheckSpecificPersonGenericDialogIsOpen(0):
        """State 5"""
        ForceCloseMenu()
    else:
        pass
    """State 8"""
    return 0

def t000001000_x2():
    """State 0,1"""
    ClearTalkProgressData()
    StopEventAnimWithoutForcingConversationEnd(0)
    ForceCloseGenericDialog()
    ForceCloseMenu()
    ReportConversationEndToHavokBehavior()
    """State 2"""
    return 0

def t000001000_x3(actionbutton1=_, flag11=6001, flag12=6000):
    """State 0"""
    while True:
        """State 1"""
        assert not GetOneLineHelpStatus() and not IsClientPlayer() and not IsPlayerDead() and not IsCharacterDisabled()
        """State 2"""
        assert CompareBonfireState(1)
        """State 4"""
        if GetEventFlag(flag12):
            """State 5"""
            assert GetEventFlag(flag11) and not GetEventFlag(flag12)
            """State 6"""
            assert GetCurrentStateElapsedTime() > 1
        elif GetEventFlag(flag11) and not GetEventFlag(flag12):
            pass
        """State 3"""
        if CompareBonfireState(0):
            pass
        elif CheckActionButtonArea(actionbutton1):
            break
        elif (not (not GetOneLineHelpStatus() and not IsClientPlayer() and not IsPlayerDead() and not IsCharacterDisabled())
              or (not GetEventFlag(flag11) or GetEventFlag(flag12))):
            pass
    """State 7"""
    return 0

def t000001000_x4(action1=_):
    """State 0,1"""
    OpenGenericDialog(DialogBoxType.CenterBottom1, action1, DialogResult.Left, DialogBoxStyle.OrnateNoOptions, 1)
    assert not CheckSpecificPersonGenericDialogIsOpen(0)
    """State 2"""
    return 0

def t000001000_x5(actionbutton5=6100, flag9=6001, flag10=6000):
    """State 0"""
    while True:
        """State 1"""
        assert not GetOneLineHelpStatus() and not IsClientPlayer() and not IsPlayerDead() and not IsCharacterDisabled()
        """State 3"""
        assert GetEventFlag(flag9) and not GetEventFlag(flag10)
        """State 2"""
        if CheckActionButtonArea(actionbutton5):
            break
        elif (not (not GetOneLineHelpStatus() and not IsClientPlayer() and not IsPlayerDead() and not IsCharacterDisabled())
              or (not GetEventFlag(flag9) or GetEventFlag(flag10))):
            pass
    """State 4"""
    return 0

def t000001000_x6(goods8=1000, goods9=10020):
    """State 0,14"""
    if GetEventFlag(720080):
        """State 15"""
        pass
    else:
        """State 16,17"""
        SetEventFlag(720080, FlagState.On)
    """State 1"""
    if GetTotalBonfireLevel() <= 13:
        """State 2,13,26"""
        call = t000001000_x17(goods8=goods8, goods11=0, z45=1)
        if call.Get() == 0:
            """State 12,25"""
            assert t000001000_x4(action1=13040150)
        elif call.Done():
            """State 11,19"""
            SetWorkValue(1, 1)
            """State 20"""
            call = t000001000_x0(action10=20011000 + GetWorkValue(1))
            if call.Get() == 0:
                """State 6,10"""
                if (ComparePlayerInventoryNumber(ItemType.Goods, goods9, CompareType.GreaterOrEqual, GetWorkValue(1),
                    False)):
                    """State 4,8"""
                    BonfireActivation(GetTotalBonfireLevel() + 1)
                    """State 9"""
                    PlayerEquipmentQuantityChange(ItemType.Goods, goods9, GetWorkValue(1) * -1)
                    """State 27"""
                    assert t000001000_x19(goods8=goods8)
                    """State 24"""
                    assert t000001000_x16(goods10=goods8)
                    """State 22"""
                    assert t000001000_x4(action1=13040020)
                    """State 18"""
                    SetWorkValue(1, 0)
                else:
                    """State 5,28"""
                    assert t000001000_x4(action1=20011000)
            elif call.Done():
                """State 7"""
                pass
    else:
        """State 3,21"""
        assert t000001000_x4(action1=13040000)
    """State 29"""
    return 0
    """Unused"""
    """State 23"""
    t000001000_x11()
    Quit()

def t000001000_x7(goods6=1000, goods7=10010):
    """State 0,15"""
    if GetEventFlag(720070):
        """State 16"""
        pass
    else:
        """State 17,18"""
        SetEventFlag(720070, FlagState.On)
    """State 1"""
    if GetEstusAllocation(EstusType.HP) + GetEstusAllocation(EstusType.FP) < 13:
        """State 2,13,26"""
        call = t000001000_x17(goods8=goods6, goods11=0, z45=1)
        if call.Get() == 0:
            """State 12,25"""
            assert t000001000_x4(action1=13040150)
        elif call.Done():
            """State 11,19"""
            SetWorkValue(1, GetEstusAllocation(EstusType.HP) + GetEstusAllocation(EstusType.FP) + -4)
            """State 28"""
            assert t000001000_x21(z32=1, z33=1, z34=2, z35=2, z36=3, z37=3, z38=4, z39=4, z40=5, z41=5, z42=1)
            """State 21"""
            call = t000001000_x0(action10=20011010 + GetWorkValue(1))
            if call.Get() == 0:
                """State 6,14"""
                if (ComparePlayerInventoryNumber(ItemType.Goods, goods7, CompareType.GreaterOrEqual, GetWorkValue(1),
                    False)):
                    """State 4,8"""
                    PlayerEquipmentQuantityChange(ItemType.Goods, goods7, GetWorkValue(1) * -1)
                    """State 9"""
                    EstusAllocationUpdate(GetEstusAllocation(EstusType.HP) + 1, 0)
                    """State 27"""
                    assert t000001000_x16(goods10=goods6)
                    """State 22"""
                    assert t000001000_x4(action1=13040140)
                    """State 20"""
                    SetWorkValue(1, 0)
                    """State 10"""
                else:
                    """State 5,23"""
                    assert t000001000_x4(action1=20011010)
            elif call.Done():
                """State 7"""
                pass
    else:
        """State 3,24"""
        assert t000001000_x4(action1=13040120)
    """State 29"""
    return 0

def t000001000_x8(goods12=1000):
    """State 0,1"""
    if (DoesPlayerHaveItem(ItemType.Goods, goods12 + 1 + 0 * 50 + 0 * 2) or DoesPlayerHaveItem(ItemType.Goods,
        goods12 + 0 + 0 * 50 + 0 * 2)):
        """State 2"""
        BonfireActivation(1)
        """State 13"""
        Label('L0')
        """State 18"""
        assert t000001000_x9(goods12=goods12)
    elif (DoesPlayerHaveItem(ItemType.Goods, goods12 + 1 + 0 * 50 + 1 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods12 + 0 + 0 * 50 + 1 * 2)):
        """State 3"""
        BonfireActivation(2)
        Goto('L0')
    elif (DoesPlayerHaveItem(ItemType.Goods, goods12 + 1 + 0 * 50 + 2 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods12 + 0 + 0 * 50 + 2 * 2)):
        """State 4"""
        BonfireActivation(3)
        Goto('L0')
    elif (DoesPlayerHaveItem(ItemType.Goods, goods12 + 1 + 0 * 50 + 3 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods12 + 0 + 0 * 50 + 3 * 2)):
        """State 5"""
        BonfireActivation(4)
        Goto('L0')
    elif (DoesPlayerHaveItem(ItemType.Goods, goods12 + 1 + 0 * 50 + 4 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods12 + 0 + 0 * 50 + 4 * 2)):
        """State 6"""
        BonfireActivation(5)
        Goto('L0')
    elif (DoesPlayerHaveItem(ItemType.Goods, goods12 + 1 + 0 * 50 + 5 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods12 + 0 + 0 * 50 + 5 * 2)):
        """State 7"""
        BonfireActivation(6)
        Goto('L0')
    elif (DoesPlayerHaveItem(ItemType.Goods, goods12 + 1 + 0 * 50 + 6 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods12 + 0 + 0 * 50 + 6 * 2)):
        """State 8"""
        BonfireActivation(7)
        Goto('L0')
    elif (DoesPlayerHaveItem(ItemType.Goods, goods12 + 1 + 0 * 50 + 7 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods12 + 0 + 0 * 50 + 7 * 2)):
        """State 9"""
        BonfireActivation(8)
        Goto('L0')
    elif (DoesPlayerHaveItem(ItemType.Goods, goods12 + 1 + 0 * 50 + 8 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods12 + 0 + 0 * 50 + 8 * 2)):
        """State 10"""
        BonfireActivation(9)
        Goto('L0')
    elif (DoesPlayerHaveItem(ItemType.Goods, goods12 + 1 + 0 * 50 + 9 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods12 + 0 + 0 * 50 + 9 * 2)):
        """State 11"""
        BonfireActivation(10)
        Goto('L0')
    elif (DoesPlayerHaveItem(ItemType.Goods, goods12 + 1 + 0 * 50 + 10 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods12 + 0 + 0 * 50 + 10 * 2)):
        """State 12"""
        BonfireActivation(11)
        Goto('L0')
    elif True:
        """State 15"""
        pass
    elif (DoesPlayerHaveItem(ItemType.Goods, goods12 + 1 + 0 * 50 + 11 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods12 + 0 + 0 * 50 + 11 * 2)):
        """State 16"""
        BonfireActivation(12)
        Goto('L0')
    elif (DoesPlayerHaveItem(ItemType.Goods, goods12 + 1 + 0 * 50 + 12 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods12 + 0 + 0 * 50 + 12 * 2)):
        """State 17"""
        BonfireActivation(13)
        Goto('L0')
    """State 14,19"""
    return 0

def t000001000_x9(goods12=1000):
    """State 0,15"""
    call = t000001000_x12(goods12=goods12, goods13=0, goods14=0)
    if call.Get() == 1:
        """State 1,11"""
        assert t000001000_x10(goods12=goods12, goods15=0, goods16=0)
    elif call.Done():
        """State 16"""
        call = t000001000_x12(goods12=goods12, goods13=0, goods14=1)
        if call.Get() == 1:
            """State 8,10"""
            assert t000001000_x10(goods12=goods12, goods15=0, goods16=1)
        elif call.Done():
            """State 2"""
            pass
    """State 5,17"""
    call = t000001000_x12(goods12=goods12, goods13=1, goods14=0)
    if call.Get() == 1:
        """State 3,13"""
        assert t000001000_x10(goods12=goods12, goods15=1, goods16=0)
    elif call.Done():
        """State 18"""
        call = t000001000_x12(goods12=goods12, goods13=1, goods14=1)
        if call.Get() == 1:
            """State 9,12"""
            assert t000001000_x10(goods12=goods12, goods15=1, goods16=1)
        elif call.Done():
            """State 4"""
            pass
    """State 6,14"""
    assert t000001000_x11()
    """State 7,19"""
    return 0

def t000001000_x10(goods12=1000, goods15=_, goods16=_):
    """State 0,1"""
    if DoesPlayerHaveItem(ItemType.Goods, goods12 + goods16 + goods15 * 50 + 0 * 2):
        """State 3"""
        ReplaceTool(goods12 + goods15 * 50 + 0 * 2 + goods16, goods12 + goods15 * 50 + goods16 + 2 * (GetTotalBonfireLevel() - 1),
                    1)
    elif DoesPlayerHaveItem(ItemType.Goods, goods12 + goods16 + goods15 * 50 + 1 * 2):
        """State 4"""
        ReplaceTool(goods12 + goods15 * 50 + 1 * 2 + goods16, goods12 + goods15 * 50 + goods16 + 2 * (GetTotalBonfireLevel() - 1),
                    1)
    elif DoesPlayerHaveItem(ItemType.Goods, goods12 + goods16 + goods15 * 50 + 2 * 2):
        """State 5"""
        ReplaceTool(goods12 + goods15 * 50 + 2 * 2 + goods16, goods12 + goods15 * 50 + goods16 + 2 * (GetTotalBonfireLevel() - 1),
                    1)
    elif DoesPlayerHaveItem(ItemType.Goods, goods12 + goods16 + goods15 * 50 + 3 * 2):
        """State 6"""
        ReplaceTool(goods12 + goods15 * 50 + 3 * 2 + goods16, goods12 + goods15 * 50 + goods16 + 2 * (GetTotalBonfireLevel() - 1),
                    1)
    elif DoesPlayerHaveItem(ItemType.Goods, goods12 + goods16 + goods15 * 50 + 4 * 2):
        """State 7"""
        ReplaceTool(goods12 + goods15 * 50 + 4 * 2 + goods16, goods12 + goods15 * 50 + goods16 + 2 * (GetTotalBonfireLevel() - 1),
                    1)
    elif DoesPlayerHaveItem(ItemType.Goods, goods12 + goods16 + goods15 * 50 + 5 * 2):
        """State 8"""
        ReplaceTool(goods12 + goods15 * 50 + 5 * 2 + goods16, goods12 + goods15 * 50 + goods16 + 2 * (GetTotalBonfireLevel() - 1),
                    1)
    elif DoesPlayerHaveItem(ItemType.Goods, goods12 + goods16 + goods15 * 50 + 6 * 2):
        """State 9"""
        ReplaceTool(goods12 + goods15 * 50 + 6 * 2 + goods16, goods12 + goods15 * 50 + goods16 + 2 * (GetTotalBonfireLevel() - 1),
                    1)
    else:
        """State 2"""
        pass
    """State 13"""
    return 0
    """Unused"""
    """State 10"""
    ReplaceTool(goods12 + goods15 * 50 + 7 * 2 + goods16, goods12 + goods15 * 50 + goods16 + 2 * (GetTotalBonfireLevel() - 1),
                1)
    Quit()
    """State 11"""
    ReplaceTool(goods12 + goods15 * 50 + 8 * 2 + goods16, goods12 + goods15 * 50 + goods16 + 2 * (GetTotalBonfireLevel() - 1),
                1)
    Quit()
    """State 12"""
    ReplaceTool(goods12 + goods15 * 50 + 9 * 2 + goods16, goods12 + goods15 * 50 + goods16 + 2 * (GetTotalBonfireLevel() - 1),
                1)
    Quit()

def t000001000_x11():
    """State 0,1,13,14"""
    return 0
    """Unused"""
    """State 2,3,4"""
    Quit()
    """State 5"""
    Quit()
    """State 6"""
    Quit()
    """State 7"""
    Quit()
    """State 8"""
    Quit()
    """State 9"""
    Quit()
    """State 10"""
    Quit()
    """State 11"""
    Quit()
    """State 12"""
    Quit()

def t000001000_x12(goods12=1000, goods13=_, goods14=_):
    """State 0,1"""
    if (not DoesPlayerHaveItem(ItemType.Goods, goods12 + goods14 + goods13 * 50 + 0 * 2) and not DoesPlayerHaveItem(ItemType.Goods,
        goods12 + goods14 + goods13 * 50 + 1 * 2) and not DoesPlayerHaveItem(ItemType.Goods, goods12 + goods14
        + goods13 * 50 + 2 * 2) and not DoesPlayerHaveItem(ItemType.Goods, goods12 + goods14 + goods13 * 50 + 3
        * 2) and not DoesPlayerHaveItem(ItemType.Goods, goods12 + goods14 + goods13 * 50 + 4 * 2) and not DoesPlayerHaveItem(ItemType.Goods,
        goods12 + goods14 + goods13 * 50 + 5 * 2) and not DoesPlayerHaveItem(ItemType.Goods, goods12 + goods14
        + goods13 * 50 + 6 * 2) and not DoesPlayerHaveItem(ItemType.Goods, goods12 + goods14 + goods13 * 50 + 7
        * 2)):
        """State 2,3"""
        return 0
    else:
        """State 4"""
        return 1

def t000001000_x13():
    """State 0,1"""
    if DoesPlayerHaveSpEffect(8990):
        """State 2"""
        GiveSpEffectToPlayer(8998)
        """State 3"""
        SetEventFlag(100210, FlagState.Off)
        SetEventFlag(100200, FlagState.Off)
    else:
        pass
    """State 4"""
    return 0

def t000001000_x14(text1=_, flag8=_, mode3=1):
    """State 0,5"""
    assert t000001000_x2() and CheckSpecificPersonTalkHasEnded(0)
    """State 1"""
    TalkToPlayer(text1, -1, -1, 0)
    assert CheckSpecificPersonTalkHasEnded(0)
    """State 4"""
    if mode3 == 0:
        pass
    else:
        """State 3"""
        ReportConversationEndToHavokBehavior()
    """State 2"""
    SetEventFlag(flag8, FlagState.On)
    """State 6"""
    return 0

def t000001000_x15(goods10=1000):
    """State 0,4,10"""
    call = t000001000_x17(goods8=goods10, goods11=0, z45=1)
    if call.Get() == 0:
        """State 2,8"""
        assert t000001000_x4(action1=13040150)
    elif call.Done():
        """State 1,7,12"""
        call = t000001000_x17(goods8=goods10, goods11=1, z45=1)
        if call.Get() == 0:
            """State 6,11"""
            assert t000001000_x4(action1=13040160)
        elif call.Done():
            """State 5,3"""
            OpenEstusAllotMenu()
            assert not (CheckSpecificPersonMenuIsOpen(14, 0) and not CheckSpecificPersonGenericDialogIsOpen(0))
            """State 9"""
            assert t000001000_x16(goods10=goods10)
    """State 13"""
    return 0

def t000001000_x16(goods10=1000):
    """State 0,3"""
    call = t000001000_x17(goods8=goods10, goods11=0, z45=1)
    if call.Get() == 1:
        """State 4"""
        assert t000001000_x18(goods10=goods10, mode2=0, z44=GetWorkValue(1))
        """State 5"""
        assert t000001000_x18(goods10=goods10, mode2=1, z44=GetWorkValue(1))
    elif call.Done():
        """State 1"""
        pass
    """State 2"""
    SetWorkValue(1, 0)
    """State 6"""
    return 0

def t000001000_x17(goods8=1000, goods11=_, z45=1):
    """State 0,13"""
    SetWorkValue(z45, 0)
    if (DoesPlayerHaveItem(ItemType.Goods, goods8 + 0 + goods11 * 50 + 0 * 2) or DoesPlayerHaveItem(ItemType.Goods,
        goods8 + 1 + goods11 * 50 + 0 * 2)):
        """State 1"""
        SetWorkValue(z45, 0)
    elif (DoesPlayerHaveItem(ItemType.Goods, goods8 + 0 + goods11 * 50 + 1 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods8 + 1 + goods11 * 50 + 1 * 2)):
        """State 2"""
        SetWorkValue(z45, 1)
    elif (DoesPlayerHaveItem(ItemType.Goods, goods8 + 0 + goods11 * 50 + 2 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods8 + 1 + goods11 * 50 + 2 * 2)):
        """State 3"""
        SetWorkValue(z45, 2)
    elif (DoesPlayerHaveItem(ItemType.Goods, goods8 + 0 + goods11 * 50 + 3 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods8 + 1 + goods11 * 50 + 3 * 2)):
        """State 4"""
        SetWorkValue(z45, 3)
    elif (DoesPlayerHaveItem(ItemType.Goods, goods8 + 0 + goods11 * 50 + 4 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods8 + 1 + goods11 * 50 + 4 * 2)):
        """State 5"""
        SetWorkValue(z45, 4)
    elif (DoesPlayerHaveItem(ItemType.Goods, goods8 + 0 + goods11 * 50 + 5 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods8 + 1 + goods11 * 50 + 5 * 2)):
        """State 6"""
        SetWorkValue(z45, 5)
    elif (DoesPlayerHaveItem(ItemType.Goods, goods8 + 0 + goods11 * 50 + 6 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods8 + 1 + goods11 * 50 + 6 * 2)):
        """State 7"""
        SetWorkValue(z45, 6)
    elif (DoesPlayerHaveItem(ItemType.Goods, goods8 + 0 + goods11 * 50 + 7 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods8 + 1 + goods11 * 50 + 7 * 2)):
        """State 8"""
        SetWorkValue(z45, 7)
    elif (DoesPlayerHaveItem(ItemType.Goods, goods8 + 0 + goods11 * 50 + 8 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods8 + 1 + goods11 * 50 + 8 * 2)):
        """State 9"""
        SetWorkValue(z45, 8)
    elif (DoesPlayerHaveItem(ItemType.Goods, goods8 + 0 + goods11 * 50 + 9 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods8 + 1 + goods11 * 50 + 9 * 2)):
        """State 10"""
        SetWorkValue(z45, 9)
    elif (DoesPlayerHaveItem(ItemType.Goods, goods8 + 0 + goods11 * 50 + 10 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods8 + 1 + goods11 * 50 + 10 * 2)):
        """State 11"""
        SetWorkValue(z45, 10)
    elif (DoesPlayerHaveItem(ItemType.Goods, goods8 + 0 + goods11 * 50 + 11 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods8 + 1 + goods11 * 50 + 11 * 2)):
        """State 14"""
        SetWorkValue(z45, 11)
    elif (DoesPlayerHaveItem(ItemType.Goods, goods8 + 0 + goods11 * 50 + 12 * 2) or DoesPlayerHaveItem(ItemType.Goods,
          goods8 + 1 + goods11 * 50 + 12 * 2)):
        """State 15"""
        SetWorkValue(z45, 12)
    else:
        """State 12"""
        SetWorkValue(z45, 13)
        """State 16"""
        return 0
    """State 17"""
    return 1

def t000001000_x18(goods10=1000, mode2=_, z44=_):
    """State 0,6"""
    if not GetEstusAllocation(mode2) < 0:
        """State 7,12"""
        if (DoesPlayerHaveItem(ItemType.Goods, goods10 + 0 + mode2 * 50 + z44 * 2) or DoesPlayerHaveItem(ItemType.Goods,
            goods10 + 1 + mode2 * 50 + z44 * 2)):
            """State 13,1"""
            if DoesPlayerHaveItem(ItemType.Goods, goods10 + 0 + mode2 * 50 + z44 * 2):
                """State 2,4"""
                ReplaceTool(1000 + mode2 * 50 + z44 * 2 + 0, 1000 + mode2 * 50 + z44 * 2 + 1, 1)
            else:
                """State 3"""
                pass
            while True:
                """State 5"""
                if (not ComparePlayerInventoryNumber(ItemType.Goods, 1000 + 1 + mode2 * 50 + z44 * 2, CompareType.GreaterOrEqual,
                    GetEstusAllocation(mode2), False)):
                    """State 9,11"""
                    PlayerEquipmentQuantityChange(ItemType.Goods, 1000 + 1 + mode2 * 50 + z44 * 2, 1)
                else:
                    """State 10"""
                    break
        else:
            """State 14"""
            pass
    else:
        """State 8"""
        pass
    """State 15"""
    return 0

def t000001000_x19(goods8=1000):
    """State 0,3"""
    call = t000001000_x17(goods8=goods8, goods11=0, z45=1)
    if call.Get() == 1:
        """State 4"""
        assert t000001000_x20(goods8=goods8, z43=GetWorkValue(1))
        """State 2"""
        SetWorkValue(1, 0)
    elif call.Done():
        """State 1"""
        pass
    """State 5"""
    return 0

def t000001000_x20(goods8=1000, z43=_):
    """State 0,1"""
    ReplaceToolIf(DoesPlayerHaveItem(ItemType.Goods, 1000 + 0 + 0 * 50 + z43 * 2), goods8 + 0 * 50 + z43 * 2 + 0,
                  goods8 + 0 * 50 + 0 + 2 * (GetTotalBonfireLevel() - 1), 1)
    """State 2"""
    ReplaceToolIf(DoesPlayerHaveItem(ItemType.Goods, 1000 + 1 + 0 * 50 + z43 * 2), goods8 + 0 * 50 + z43 * 2 + 1,
                  goods8 + 0 * 50 + 1 + 2 * (GetTotalBonfireLevel() - 1), 1)
    """State 3"""
    ReplaceToolIf(DoesPlayerHaveItem(ItemType.Goods, 1000 + 0 + 1 * 50 + z43 * 2), goods8 + 1 * 50 + z43 * 2 + 0,
                  goods8 + 1 * 50 + 0 + 2 * (GetTotalBonfireLevel() - 1), 1)
    """State 4"""
    ReplaceToolIf(DoesPlayerHaveItem(ItemType.Goods, 1000 + 1 + 1 * 50 + z43 * 2), goods8 + 1 * 50 + z43 * 2 + 1,
                  goods8 + 1 * 50 + 1 + 2 * (GetTotalBonfireLevel() - 1), 1)
    """State 5"""
    return 0

def t000001000_x21(z32=1, z33=1, z34=2, z35=2, z36=3, z37=3, z38=4, z39=4, z40=5, z41=5, z42=1):
    """State 0"""
    if GetWorkValue(z42) == 0:
        """State 1"""
        SetWorkValue(z42, z32)
    elif GetWorkValue(z42) == 1:
        """State 2"""
        SetWorkValue(z42, z33)
    elif GetWorkValue(z42) == 2:
        """State 3"""
        SetWorkValue(z42, z34)
    elif GetWorkValue(z42) == 3:
        """State 4"""
        SetWorkValue(z42, z35)
    elif GetWorkValue(z42) == 4:
        """State 5"""
        SetWorkValue(z42, z36)
    elif GetWorkValue(z42) == 5:
        """State 6"""
        SetWorkValue(z42, z37)
    elif GetWorkValue(z42) == 6:
        """State 7"""
        SetWorkValue(z42, z38)
    elif GetWorkValue(z42) == 7:
        """State 8"""
        SetWorkValue(z42, z39)
    elif GetWorkValue(z42) == 8:
        """State 9"""
        SetWorkValue(z42, z40)
    elif GetWorkValue(z42) == 9:
        """State 10"""
        SetWorkValue(z42, z41)
    else:
        """State 11"""
        SetWorkValue(z42, 5)
    """State 12"""
    return 0

def t000001000_x22():
    """State 0"""
    if not GetEventFlag(9000):
        """State 3,1"""
        SetEventFlag(4652, FlagState.Off)
        SetEventFlag(4653, FlagState.Off)
        SetEventFlag(4654, FlagState.Off)
        SetEventFlag(4655, FlagState.Off)
        SetEventFlag(4656, FlagState.Off)
        SetEventFlag(4657, FlagState.Off)
        SetEventFlag(4651, FlagState.Off)
    else:
        """State 2"""
        pass
    while True:
        """State 4"""
        if IsMultiplayerInProgress() and not GetEventFlag(2051) and not GetEventFlag(2052):
            """State 6"""
            call = t000001000_x25()
            assert not IsMultiplayerInProgress() or GetEventFlag(2051) or GetEventFlag(2052)
        elif GetEventFlag(1042369415):
            """State 7"""
            call = t000001000_x63()
            assert not GetEventFlag(1042369415)
        else:
            """State 5"""
            def WhilePaused():
                GiveSpEffectToPlayerIf(GetEventFlag(9000) and GetWorkValue(0) == 0, 9607)
                GiveSpEffectToPlayerIf(GetEventFlag(9000) and GetWorkValue(0) == 10, 9608)
                GiveSpEffectToPlayerIf(GetEventFlag(9000) and GetDistanceToPlayer() < 1.05, 9609)
                GiveSpEffectToPlayerIf(GetEventFlag(4698) and GetEventFlag(9001), 9606)
            assert t000001000_x23()
    """Unused"""
    """State 8"""
    return 0

def t000001000_x23():
    """State 0,1"""
    if CompareBonfireLevel(CompareType.LessOrEqual, 0) or GetEventFlag(11102790):
        """State 2"""
        Label('L0')
        assert GetWhetherChrEventAnimHasEnded(10000)
    else:
        """State 3,32"""
        call = t000001000_x40()
        if call.Done():
            """State 7"""
            TurnCharacterToFaceEntity(-1, 10000, -1, -1)
            assert GetCurrentStateElapsedFrames() > 1 and GetWhetherChrEventAnimHasEnded(10000)
            """State 4"""
            OfferHumanity()
            assert CompareBonfireLevel(CompareType.LessOrEqual, 0)
            """State 9,10"""
            UpdatePlayerRespawnPoint()
            Goto('L0')
        elif CompareBonfireLevel(CompareType.LessOrEqual, 0) or GetEventFlag(11102790):
            pass
    """State 33"""
    call = t000001000_x40()
    if call.Done():
        """State 5"""
        ClearPlayerDamageInfo()
        """State 11"""
        GiveSpEffectToPlayer(202)
        """State 6"""
        SetTalkTime(1)
        """State 37"""
        assert t000001000_x67()
        """State 23"""
        SetEventFlag(4698, FlagState.Off)
        SetEventFlagIf(DoesSelfHaveSpEffect(9680) and not GetEventFlag(953), 4698, FlagState.On)
        SetEventFlagIf(GetEventFlagValue(955, 3) > 2 and DoesSelfHaveSpEffect(9681) and not GetEventFlag(953),
                       4698, FlagState.On)
        """State 30"""
        assert t000001000_x32()
        """State 8"""
        TurnCharacterToFaceEntity(-1, 10000, -1, -1)
        assert GetCurrentStateElapsedFrames() > 1 and GetWhetherChrEventAnimHasEnded(10000)
        """State 12"""
        UpdatePlayerRespawnPoint()
        """State 40"""
        assert t000001000_x82()
        """State 19"""
        StartBonfireAnimLoop(1, 1, 1, 1, GetWorkValue(0), 0.5)
        """State 13"""
        FadeOutAndPassTime(0, 0, 0, 0, 0, 0, 0, 0.1, 0, 1.5, 0, 0.75, 0.5)
        """State 18"""
        SetEventFlag(9000, FlagState.On)
        SetEventFlag(9020, FlagState.On)
        ChangeCameraIf(not GetEventFlag(11102790), 1001000)
        ChangeCameraIf(GetEventFlag(11102790), 1001001)
        if not GetEventFlag(4698):
            """State 36"""
            assert t000001000_x66()
        else:
            """State 35"""
            assert t000001000_x64()
        """State 17"""
        if not GetEventFlag(9001):
            """State 21"""
            pass
        else:
            """State 20"""
            assert not GetEventFlag(9001)
        """State 41"""
        call = t000001000_x84()
        if call.Get() == 0:
            """State 26"""
            pass
        elif call.Get() == 1:
            """State 27,29"""
            assert t000001000_x30()
        """State 15"""
        if not GetEventFlag(4653):
            """State 22,39"""
            Label('L1')
            assert t000001000_x68()
            """State 31"""
            call = t000001000_x31()
            def WhilePaused():
                GiveSpEffectToPlayerIf(GetEventFlag(4651), 9620)
            def ExitPause():
                EndBonfireKindleAnimLoop(GetWorkValue(0))
            if call.Done():
                pass
            elif ((((GetDistanceToPlayer() > 3 and not GetEventFlag(11102790)) or GetDistanceToPlayer() > 7) and
                  GetCurrentStateElapsedFrames() > 1) or (CompareBonfireState(0) and GetCurrentStateElapsedFrames()
                  > 1) or (HasPlayerBeenAttacked() and GetCurrentStateElapsedFrames() > 1) or (IsMultiplayerInProgress()
                  and not GetEventFlag(2051) and not GetEventFlag(2052) and GetCurrentStateElapsedFrames() > 1)
                  or (GetEventFlag(1042369415) and GetCurrentStateElapsedFrames() > 1) or (CompareBonfireLevel(CompareType.Equal,
                  0) and not GetEventFlag(11102790) and GetCurrentStateElapsedFrames() > 1)):
                """State 28"""
                Label('L2')
                assert t000001000_x24()
        else:
            """State 16,34"""
            call = t000001000_x50()
            if call.Done():
                Goto('L1')
            elif ((GetEventFlag(1042369415) and GetCurrentStateElapsedFrames() > 1) or (IsMultiplayerInProgress()
                  and GetCurrentStateElapsedFrames() > 1) or (HasPlayerBeenAttacked() and GetCurrentStateElapsedFrames()
                  > 1) or (((GetDistanceToPlayer() > 3 and not GetEventFlag(11102790)) or GetDistanceToPlayer()
                  > 7) and GetCurrentStateElapsedFrames() > 1) or (CompareBonfireState(0) and GetCurrentStateElapsedFrames()
                  > 1)):
                """State 24"""
                def ExitPause():
                    EndBonfireKindleAnimLoop(GetWorkValue(0))
                Goto('L2')
        """State 38"""
        assert t000001000_x67()
        """State 14"""
        SetEventFlag(9000, FlagState.Off)
        SetEventFlag(9020, FlagState.Off)
        ChangeCamera(-1)
        SetCanOpenMap(False)
        assert GetCurrentStateElapsedFrames() > 1
        """State 25"""
        if not IsMultiplayerInProgress() and not GetEventFlag(1042369415):
            Goto('L0')
        else:
            pass
    elif (GetEventFlag(1042369415) or (CompareBonfireLevel(CompareType.Equal, 0) and not GetEventFlag(11102790))
          or (IsMultiplayerInProgress() and not GetEventFlag(2051) and not GetEventFlag(2052))):
        pass
    """State 42"""
    return 0

def t000001000_x24():
    """State 0,1"""
    assert t000001000_x1()
    """State 2"""
    return 0

def t000001000_x25():
    """State 0"""
    while True:
        """State 1"""
        call = t000001000_x26()
        assert IsClientPlayer()
        """State 2"""
        call = t000001000_x27()
        assert not IsClientPlayer()
    """Unused"""
    """State 3"""
    return 0

def t000001000_x26():
    """State 0,6"""
    call = t000001000_x1()
    if call.Done() and CompareBonfireLevel(CompareType.LessOrEqual, 0):
        pass
    elif call.Done():
        """State 2,7"""
        call = t000001000_x3(actionbutton1=6100, flag11=6001, flag12=6000)
        if call.Done():
            """State 4"""
            TurnCharacterToFaceEntity(-1, 10000, -1, -1)
            assert GetCurrentStateElapsedFrames() > 1 and GetWhetherChrEventAnimHasEnded(10000)
            """State 3"""
            OfferHumanity()
            """State 5"""
            UpdatePlayerRespawnPoint()
            assert CompareBonfireLevel(CompareType.LessOrEqual, 0)
        elif CompareBonfireLevel(CompareType.LessOrEqual, 0):
            pass
    """State 1"""
    Quit()
    """Unused"""
    """State 8"""
    return 0

def t000001000_x27():
    """State 0,1"""
    assert t000001000_x1()
    """State 2"""
    return 0

def t000001000_x28():
    """State 0,1"""
    if not GetEventFlag(4651):
        """State 3"""
        if GetEventFlag(4698):
            """State 5,10"""
            assert t000001000_x35(z27=20006, val4=0.5, z28=1, z29=2, z30=60)
        elif GetEventFlag(108):
            """State 9,13"""
            assert t000001000_x35(z27=20000, val4=3.5, z28=1, z29=2, z30=60)
        else:
            """State 4,6"""
            if not GetEventFlag(400001):
                """State 7,11"""
                assert t000001000_x35(z27=20000, val4=3.5, z28=1, z29=2, z30=60)
            else:
                """State 8,12"""
                assert t000001000_x35(z27=20001, val4=3.5, z28=1, z29=2, z30=60)
    else:
        """State 2"""
        pass
    """State 14"""
    return 0

def t000001000_x29(z31=_):
    """State 0,1"""
    RemoveDynamicCharacter(z31, 1.4)
    """State 2"""
    SetEventFlag(4651, FlagState.Off)
    SetEventFlag(4652, FlagState.Off)
    SetEventFlag(4653, FlagState.Off)
    SetEventFlag(4654, FlagState.Off)
    SetEventFlag(4655, FlagState.Off)
    SetEventFlag(4656, FlagState.Off)
    SetEventFlag(4657, FlagState.Off)
    """State 3"""
    return 0

def t000001000_x30():
    """State 0"""
    if GetEventFlag(11102790):
        """State 3"""
        pass
    elif GetEventFlag(110):
        """State 1"""
        pass
    elif not GetEventFlag(953) or GetEventFlag(4698):
        """State 4"""
        assert t000001000_x59()
    elif not GetEventFlag(4680):
        """State 2"""
        pass
    elif GetEventFlag(108):
        """State 7"""
        assert t000001000_x62()
    elif GetEventFlag(11009260) and not GetEventFlag(400001):
        """State 6"""
        assert t000001000_x61()
    else:
        """State 5"""
        assert t000001000_x60()
    """State 8"""
    return 0

def t000001000_x31():
    """State 0,10"""
    assert GetCurrentStateElapsedTime() > 0.1 or not GetEventFlag(4651)
    """State 11"""
    assert not GetEventFlag(9001)
    """State 28"""
    assert t000001000_x8(goods12=1000)
    """State 5"""
    ClearPreviousMenuSelection()
    while True:
        """State 1"""
        Label('L0')
        ClearTalkListData()
        """State 2"""
        AddTalkListDataIf(not GetEventFlag(9411) or GetEventFlag(9412), 1, 15000420, -1)
        AddTalkListDataIf(GetEventFlag(4680) or GetEventFlag(4699), 2, 15000540, -1)
        """State 39"""
        assert t000001000_x71(z19=3, action7=15000371)
        """State 42"""
        assert t000001000_x80(z2=50, action5=20010001, goods2=2010000, goods3=2010100)
        """State 17"""
        AddTalkListData(4, 15000390, -1)
        AddTalkListDataIf(ComparePlayerInventoryNumber(ItemType.Goods, 250, CompareType.Greater, 0, False) or ComparePlayerInventoryNumber(ItemType.Goods, 251, CompareType.Greater, 0, False),
                          5, 15000510, -1)
        AddTalkListData(6, 15000395, -1)
        AddTalkListDataIf(PlayerHasTool(15), 7, 15000520, -1)
        AddTalkListDataIf(ComparePlayerInventoryNumber(ItemType.Goods, 8590, CompareType.GreaterOrEqual, 1, False),
                          8, 15000530, -1)
        AddTalkListDataIf(ComparePlayerInventoryNumber(ItemType.Goods, 8163, CompareType.Greater, 0, False) or ComparePlayerInventoryNumber(ItemType.Goods, 8188, CompareType.Greater, 0, False),
                          9, 22230000, -1)
        """State 46"""
        assert t000001000_x85()
        """State 45"""
        call = t000001000_x84()
        if call.Get() == 0:
            """State 25"""
            pass
        elif call.Get() == 1:
            """State 26,36"""
            assert t000001000_x52()
        """State 15"""
        AddTalkListData(99, 20000009, -1)
        """State 6"""
        SetEventFlag(4652, FlagState.Off)
        SetEventFlag(4656, FlagState.Off)
        SetEventFlag(4654, FlagState.Off)
        SetEventFlag(4655, FlagState.Off)
        """State 3"""
        SetCanOpenMap(True)
        ShowShopMessage(TalkOptionsType.Regular)
        assert not (CheckSpecificPersonMenuIsOpen(1, 0) and not CheckSpecificPersonGenericDialogIsOpen(0))
        """State 8"""
        if GetTalkListEntryResult() == 1:
            """State 29"""
            SetCanOpenMap(False)
            ClearPreviousMenuSelection()
            def ExitPause():
                ClearPreviousMenuSelection()
            assert t000001000_x33()
        elif GetTalkListEntryResult() == 2:
            """State 18"""
            if not GetEventFlag(2051) and not GetEventFlag(2052):
                """State 19,30"""
                assert t000001000_x34()
            else:
                """State 20,40"""
                assert t000001000_x4(action1=20011032)
        elif GetTalkListEntryResult() == 3:
            """State 35"""
            SetCanOpenMap(False)
            ClearPreviousMenuSelection()
            def ExitPause():
                ClearPreviousMenuSelection()
            assert t000001000_x47()
        elif GetTalkListEntryResult() == 4:
            """State 7"""
            OpenMagicEquip(-1, -1)
            assert not (CheckSpecificPersonMenuIsOpen(11, 0) and not CheckSpecificPersonGenericDialogIsOpen(0))
        elif GetTalkListEntryResult() == 5:
            """State 12"""
            OpenPhysickMenu()
            assert not (CheckSpecificPersonMenuIsOpen(21, 0) and not CheckSpecificPersonGenericDialogIsOpen(0))
        elif GetTalkListEntryResult() == 6:
            """State 9"""
            OpenRepository()
            assert not (CheckSpecificPersonMenuIsOpen(3, 0) and not CheckSpecificPersonGenericDialogIsOpen(0))
        elif GetTalkListEntryResult() == 7:
            """State 13"""
            OpenGreatRuneEquipMenu()
            assert not (CheckSpecificPersonMenuIsOpen(24, 0) and not CheckSpecificPersonGenericDialogIsOpen(0))
        elif GetTalkListEntryResult() == 8:
            """State 14"""
            OpenEquipmentChangeOfPurposeShop()
            assert not (CheckSpecificPersonMenuIsOpen(7, 0) and not CheckSpecificPersonGenericDialogIsOpen(0))
        elif GetTalkListEntryResult() == 9:
            """State 16"""
            OpenTailoringShop(111000, 111399)
            assert not (CheckSpecificPersonMenuIsOpen(26, 0) and not CheckSpecificPersonGenericDialogIsOpen(0))
        elif GetTalkListEntryResult() == 11:
            """State 31"""
            assert t000001000_x36(flag7=4655)
        elif GetTalkListEntryResult() == 12:
            """State 38"""
            assert t000001000_x36(flag7=4657)
        elif GetTalkListEntryResult() == 15:
            """State 37"""
            assert t000001000_x54()
        elif GetTalkListEntryResult() == 32:
            """State 33"""
            assert t000001000_x38()
        elif GetTalkListEntryResult() == 41 and GetEventFlag(120) and GetEventFlag(11102790):
            """State 21"""
            if not GetEventFlag(2051) and not GetEventFlag(2052):
                """State 22,34"""
                assert t000001000_x42()
            else:
                """State 23,41"""
                assert t000001000_x4(action1=20011031)
        elif GetTalkListEntryResult() == 50:
            """State 24,43"""
            SetCanOpenMap(False)
            ClearPreviousMenuSelection()
            def ExitPause():
                ClearPreviousMenuSelection()
            assert t000001000_x78(goods4=2010000, goods5=2010100)
        elif GetTalkListEntryResult() == 75:
            """State 27,47"""
            SetCanOpenMap(False)
            ClearPreviousMenuSelection()
            def ExitPause():
                ClearPreviousMenuSelection()
            assert t000001000_x87()
        else:
            """State 4,44"""
            assert t000001000_x83()
            """State 48"""
            return 0
    """Unused"""
    """State 32"""
    assert t000001000_x37()
    Goto('L0')

def t000001000_x32():
    """State 0,1"""
    if GetEventFlag(1054532702):
        """State 2,4"""
        Label('L0')
        """State 3"""
        SetWorkValue(0, 0)
    elif GetEventFlag(4698):
        """State 8"""
        Goto('L0')
    elif GetEventFlag(11102790):
        """State 6,7"""
        SetWorkValue(0, 30)
    else:
        """State 5,9"""
        assert t000001000_x39()
    """State 10"""
    return 0

def t000001000_x33():
    """State 0,5"""
    CloseShopMessage()
    while True:
        """State 1"""
        ClearTalkListData()
        """State 2"""
        AddTalkListData(1, 15000430, -1)
        AddTalkListData(2, 15000440, -1)
        AddTalkListData(3, 15000450, -1)
        AddTalkListData(99, 15000460, -1)
        """State 3"""
        ShowShopMessage(TalkOptionsType.Regular)
        assert not (CheckSpecificPersonMenuIsOpen(1, 0) and not CheckSpecificPersonGenericDialogIsOpen(0))
        """State 6"""
        if GetTalkListEntryResult() == 1:
            """State 7"""
            def ExitPause():
                HideClock(0.5)
            assert t000001000_x45(val1=0)
        elif GetTalkListEntryResult() == 2:
            """State 8"""
            def ExitPause():
                HideClock(0.5)
            assert t000001000_x45(val1=1)
        elif GetTalkListEntryResult() == 3:
            """State 9"""
            def ExitPause():
                HideClock(0.5)
            assert t000001000_x45(val1=2)
        else:
            """State 4,10"""
            assert t000001000_x72()
            """State 11"""
            return 0

def t000001000_x34():
    """State 0"""
    if not GetEventFlag(4651):
        """State 3,4"""
        OpenSoul()
        assert not (CheckSpecificPersonMenuIsOpen(10, 0) and not CheckSpecificPersonGenericDialogIsOpen(0))
    else:
        """State 2,1"""
        SetEventFlag(4652, FlagState.On)
        SetEventFlag(4656, FlagState.On)
        """State 5"""
        assert not GetEventFlag(4652)
        """State 6"""
        SetWorkValue(0, 0)
    """State 7"""
    return 0

def t000001000_x35(z27=_, val4=_, z28=1, z29=2, z30=60):
    """State 0,4"""
    assert not DoesPlayerHaveSpEffect(9600) and not DoesPlayerHaveSpEffect(9603)
    """State 1"""
    SpawnDynamicCharacter(2180, 21800000, 1, 3000, z27, z28, z29, z30)
    """State 2"""
    SetEventFlag(4651, FlagState.On)
    """State 3"""
    assert GetCurrentStateElapsedTime() > val4
    """State 5"""
    return 0

def t000001000_x36(flag7=_):
    """State 0"""
    if not GetEventFlag(4651):
        """State 1,8"""
        assert t000001000_x28()
    else:
        """State 4"""
        pass
    """State 3"""
    SetEventFlag(4652, FlagState.On)
    SetEventFlag(flag7, FlagState.On)
    """State 2"""
    assert (not GetEventFlag(4652) or (GetCurrentStateElapsedTime() > 5 and not DoesPlayerHaveSpEffect(9600) and
            not DoesPlayerHaveSpEffect(9603)))
    """State 5"""
    if not GetEventFlag(4680):
        """State 6,9"""
        assert t000001000_x29(z31=20010)
    else:
        """State 7"""
        pass
    """State 10"""
    return 0

def t000001000_x37():
    """State 0,1"""
    SetEventFlag(1054539200, FlagState.On)
    """State 4"""
    assert t000001000_x28()
    """State 2"""
    SetEventFlag(4652, FlagState.On)
    """State 3"""
    assert not GetEventFlag(4652)
    """State 5"""
    return 0

def t000001000_x38():
    """State 0,1"""
    SetEventFlag(1054539201, FlagState.On)
    """State 2"""
    SetEventFlag(1054539205, FlagState.On)
    """State 3"""
    assert GetCurrentStateElapsedTime() > 1.5
    """State 5"""
    SetEventFlag(9000, FlagState.Off)
    SetEventFlag(9020, FlagState.Off)
    """State 4"""
    ChangeCamera(-1)
    Quit()
    """Unused"""
    """State 6"""
    return 0

def t000001000_x39():
    """State 0,1"""
    if not CompareRNGValue(CompareType.Equal, 0) != -1:
        """State 3,4"""
        ShuffleRNGSeed(100)
    else:
        """State 2"""
        pass
    """State 5"""
    SetRNGSeed()
    """State 6"""
    if CompareRNGValue(CompareType.Less, 69) == True:
        """State 7,8"""
        SetWorkValue(0, 0)
    elif CompareRNGValue(CompareType.Less, 99) == True:
        """State 9,10"""
        SetWorkValue(0, 10)
    else:
        """State 11,12"""
        SetWorkValue(0, 0)
    """State 13"""
    return 0

def t000001000_x40():
    """State 0"""
    while True:
        """State 1"""
        if GetEventFlag(1054532702):
            """State 2,7"""
            call = t000001000_x65(actionbutton1=6100, actionbutton2=6101, val2=45, z22=-120)
            if call.Done():
                break
            elif not GetEventFlag(1054532702):
                pass
        elif GetEventFlag(11102790):
            """State 4,6"""
            call = t000001000_x44(actionbutton3=6102, actionbutton4=6103, val3=45)
            if call.Done():
                break
            elif not GetEventFlag(11102790):
                pass
        else:
            """State 3,5"""
            call = t000001000_x41(actionbutton1=6100, actionbutton2=6101)
            if call.Done():
                break
            elif GetEventFlag(1054532702) or GetEventFlag(11102790):
                pass
    """State 8"""
    return 0

def t000001000_x41(actionbutton1=_, actionbutton2=_):
    """State 0,1"""
    if CompareBonfireLevel(CompareType.Equal, 0):
        """State 2,4"""
        assert t000001000_x3(actionbutton1=actionbutton1, flag11=6001, flag12=6000)
    else:
        """State 3,5"""
        assert t000001000_x3(actionbutton1=actionbutton2, flag11=6001, flag12=6000)
    """State 6"""
    return 0

def t000001000_x42():
    """State 0,7"""
    call = t000001000_x0(action10=20011080)
    if call.Get() == 0:
        """State 2,8"""
        call = t000001000_x0(action10=20011081)
        if call.Get() == 0:
            """State 3,5"""
            SetEventFlag(3001, FlagState.On)
            """State 6"""
            Quit()
        elif call.Done():
            """State 4"""
            pass
    elif call.Done():
        """State 1"""
        pass
    """State 9"""
    return 0

def t000001000_x43(z23=11, z24=12):
    """State 0,2"""
    SetEventFlag(1042379200, FlagState.Off)
    SetEventFlag(1042379202, FlagState.Off)
    SetEventFlag(1042379206, FlagState.Off)
    SetEventFlag(1046389201, FlagState.Off)
    SetEventFlag(1043349250, FlagState.Off)
    SetEventFlag(1038509250, FlagState.Off)
    SetEventFlag(1043539250, FlagState.Off)
    SetEventFlag(11009255, FlagState.Off)
    SetEventFlag(1043509200, FlagState.Off)
    SetEventFlag(1054559200, FlagState.Off)
    SetEventFlag(1036489250, FlagState.Off)
    SetEventFlag(1039519250, FlagState.Off)
    SetEventFlag(1037519200, FlagState.Off)
    SetEventFlag(10009656, FlagState.Off)
    SetEventFlag(11009270, FlagState.Off)
    SetEventFlag(11009275, FlagState.Off)
    SetEventFlag(1054539210, FlagState.Off)
    SetEventFlag(35009350, FlagState.Off)
    SetEventFlag(35009352, FlagState.Off)
    SetEventFlag(1054539215, FlagState.Off)
    """State 4"""
    SetEventFlag(1042379208, FlagState.Off)
    SetEventFlag(11009265, FlagState.Off)
    SetEventFlag(35009355, FlagState.Off)
    SetEventFlag(35009358, FlagState.Off)
    if not GetEventFlag(953):
        """State 1"""
        if not GetEventFlag(4699):
            pass
        else:
            """State 8"""
            assert t000001000_x46(z24=z23)
    elif GetEventFlag(11102790):
        """State 3"""
        pass
    elif GetEventFlag(11009260) and not GetEventFlag(400001):
        """State 5"""
        pass
    elif GetEventFlag(108):
        """State 7"""
        pass
    elif GetEventFlag(110):
        """State 6"""
        pass
    else:
        """State 9"""
        assert t000001000_x49(z23=z23, z24=z24)
    """State 10"""
    return 0

def t000001000_x44(actionbutton3=6102, actionbutton4=6103, val3=45):
    """State 0"""
    if GetRelativeAngleBetweenPlayerAndSelf() < val3:
        """State 1"""
        Label('L0')
        """State 3"""
        call = t000001000_x41(actionbutton1=actionbutton3, actionbutton2=actionbutton4)
        if call.Done():
            """State 4"""
            return 0
        elif not GetRelativeAngleBetweenPlayerAndSelf() < val3:
            pass
    else:
        pass
    """State 2"""
    assert GetRelativeAngleBetweenPlayerAndSelf() < val3
    Goto('L0')

def t000001000_x45(val1=_):
    """State 0,8"""
    assert t000001000_x13()
    """State 10"""
    assert t000001000_x74(val1=val1)
    """State 4"""
    if val1 == 0:
        """State 1"""
        ShowClock(2)
        SetCurrentTime(0, 0, 0, 0, GetMorningHours(), GetMorningMinutes(), GetMorningSeconds(), 2.5, 0.75, 2, 0, 0.75, 0.5)
    elif val1 == 1:
        """State 2"""
        ShowClock(2)
        SetCurrentTime(0, 0, 0, 0, GetNoonHours(), GetNoonMinutes(), GetNoonSeconds(), 2.5, 0.75, 2, 0, 0.75, 0.5)
    elif val1 == 2:
        """State 3"""
        ShowClock(2)
        SetCurrentTime(0, 0, 0, 0, GetNightHours(), GetNightMinutes(), GetNightSeconds(), 2.5, 0.75, 2, 0, 0.75, 0.5)
    """State 5"""
    assert GetCurrentStateElapsedTime() > 0.8
    """State 9"""
    assert t000001000_x29(z31=0)
    """State 6"""
    assert IsTimePassFadeOutInProgress() == False
    """State 7"""
    assert GetCurrentStateElapsedTime() > 2.5
    """State 11"""
    return 0

def t000001000_x46(z24=_):
    """State 0,1"""
    AddTalkListData(z24, 99990301, -1)
    """State 2"""
    return 0

def t000001000_x47():
    """State 0,13"""
    assert t000001000_x48()
    """State 5"""
    CloseShopMessage()
    while True:
        """State 1"""
        ClearTalkListData()
        """State 14"""
        assert t000001000_x69(z21=1, action9=15000370)
        """State 15"""
        assert t000001000_x70(z20=2, action8=15000380)
        """State 2"""
        AddTalkListData(3, 15000385, -1)
        AddTalkListData(99, 15000372, -1)
        """State 3"""
        ShowShopMessage(TalkOptionsType.Regular)
        assert not (CheckSpecificPersonMenuIsOpen(1, 0) and not CheckSpecificPersonGenericDialogIsOpen(0))
        """State 6"""
        if GetTalkListEntryResult() == 1:
            """State 10"""
            assert t000001000_x7(goods6=1000, goods7=10010)
        elif GetTalkListEntryResult() == 2:
            """State 7"""
            if not GetEventFlag(2051) and not GetEventFlag(2052):
                """State 8,11"""
                assert t000001000_x6(goods8=1000, goods9=10020)
            else:
                """State 9,16"""
                assert t000001000_x4(action1=20011030)
        elif GetTalkListEntryResult() == 3:
            """State 12"""
            assert t000001000_x15(goods10=1000)
        else:
            """State 4,17"""
            return 0

def t000001000_x48():
    """State 0"""
    if not GetEventFlag(720070) or not GetEventFlag(720080):
        """State 1,3"""
        SetEventFlag(720070, FlagState.On)
        SetEventFlag(720080, FlagState.On)
        """State 4"""
    else:
        """State 2"""
        pass
    """State 5"""
    return 0

def t000001000_x49(z23=11, z24=12):
    """State 0"""
    assert GetCurrentStateElapsedFrames() > 1
    """State 1"""
    assert t000001000_x57(z23=z23)
    """State 2"""
    assert t000001000_x58(z24=z24)
    """State 3"""
    return 0

def t000001000_x50():
    """State 0,9"""
    assert t000001000_x28()
    """State 7"""
    SetEventFlag(4652, FlagState.On)
    """State 4"""
    assert (not GetEventFlag(4652) or (GetCurrentStateElapsedTime() > 5 and not DoesPlayerHaveSpEffect(9600) and
            not DoesPlayerHaveSpEffect(9603)))
    """State 1"""
    if not GetEventFlag(4680):
        """State 2,8"""
        Label('L0')
        assert t000001000_x29(z31=20010) and GetCurrentStateElapsedTime() > 3
    elif GetEventFlag(108):
        """State 6"""
        Goto('L0')
    elif GetEventFlag(11009260) and not GetEventFlag(400001):
        """State 5"""
        Goto('L0')
    else:
        """State 3"""
        pass
    """State 10"""
    return 0

def t000001000_x51(z26=15):
    """State 0"""
    if not GetEventFlag(12019257):
        """State 1"""
        if not GetEventFlag(12019255):
            """State 5"""
            AddTalkListDataAlt(z26, 21060900, -1, 0, False)
        elif not GetEventFlag(12019256):
            """State 6"""
            AddTalkListDataAlt(z26, 21060901, -1, 0, False)
        else:
            """State 7"""
            AddTalkListDataAlt(z26, 21060902, -1, 0, False)
    elif not GetEventFlag(12019260):
        """State 2"""
        if not GetEventFlag(12012711):
            """State 8"""
            AddTalkListDataAltIf(not GetEventFlag(12019258), z26, 21060903, -1, 0, False)
            AddTalkListDataAltIf(GetEventFlag(12019258), z26, 21060903, -1, 0, False)
        elif GetEventFlag(1045379208):
            """State 9"""
            AddTalkListDataAlt(z26, 21060910, -1, 0, True)
        else:
            """State 13"""
            AddTalkListDataAlt(z26, 21060911, -1, 0, True)
    elif not GetEventFlag(12019265):
        """State 3"""
        if not GetEventFlag(12012712) or not GetEventFlag(1045379208):
            """State 10"""
            AddTalkListDataAltIf(not GetEventFlag(12019261), z26, 21060912, -1, 0, False)
            AddTalkListDataAltIf(GetEventFlag(12019261), z26, 21060912, -1, 0, False)
        else:
            """State 11"""
            AddTalkListDataAlt(z26, 21060920, -1, 0, True)
    else:
        """State 4,12"""
        AddTalkListDataAltIf(not GetEventFlag(12019266), z26, 21060921, -1, 0, True)
        AddTalkListDataAltIf(GetEventFlag(12019266), z26, 21060921, -1, 0, False)
    """State 14"""
    return 0

def t000001000_x52():
    """State 0"""
    if (GetEventFlag(400394) and not GetEventFlag(12019280) and (GetEventFlag(12012710) or GetEventFlag(12012711)
        or GetEventFlag(12012712))):
        """State 4"""
        assert t000001000_x51(z26=15)
    elif GetEventFlag(400394) and GetEventFlag(1034509406) and GetEventFlag(12012713):
        """State 5"""
        assert t000001000_x53(z25=15)
    else:
        """State 3"""
        assert t000001000_x43(z23=11, z24=12)
    """State 1"""
    AddTalkListDataAltIf(GetEventFlag(1054532702) and GetEventFlag(108) and not GetEventFlag(110), 32, 20010101,
                         -1, 0, True)
    AddTalkListDataIf(GetEventFlag(120) and GetEventFlag(11102790), 41, 20010080, -1)
    """State 6"""
    return 0
    """Unused"""
    """State 2"""
    Quit()

def t000001000_x53(z25=15):
    """State 0"""
    if not GetEventFlag(12019275):
        """State 1"""
        AddTalkListDataAlt(z25, 21060930, -1, 0, False)
    else:
        """State 2"""
        AddTalkListDataAltIf(not GetEventFlag(12019276), z25, 21060931, -1, 0, False)
        AddTalkListDataAltIf(GetEventFlag(12019276), z25, 21060931, -1, 0, False)
    """State 3"""
    return 0

def t000001000_x54():
    """State 0"""
    if not GetEventFlag(12012713):
        """State 1"""
        assert t000001000_x55()
    else:
        """State 2"""
        assert t000001000_x56()
    """State 3"""
    return 0

def t000001000_x55():
    """State 0"""
    if not GetEventFlag(12019257):
        """State 1"""
        if not GetEventFlag(12019255):
            """State 5"""
            assert t000001000_x14(text1=10619000, flag8=12019255, mode3=1)
        elif not GetEventFlag(12019256):
            """State 6"""
            assert t000001000_x14(text1=10619100, flag8=12019256, mode3=1)
        else:
            """State 7"""
            call = t000001000_x14(text1=10619200, flag8=12019257, mode3=1)
            assert call.Done() or call.Done()
    elif not GetEventFlag(12019260):
        """State 2"""
        if not GetEventFlag(12012711):
            """State 11"""
            assert t000001000_x14(text1=10619300, flag8=12019258, mode3=1)
        elif GetEventFlag(1045379208):
            """State 8"""
            assert t000001000_x14(text1=10620000, flag8=12019260, mode3=1)
        else:
            """State 9"""
            assert t000001000_x14(text1=10603000, flag8=12019260, mode3=1)
    elif not GetEventFlag(12019265):
        """State 3"""
        if not GetEventFlag(12012712) or not GetEventFlag(1045379208):
            """State 12"""
            assert t000001000_x14(text1=10620100, flag8=12019261, mode3=1)
        else:
            """State 10"""
            assert t000001000_x14(text1=10621000, flag8=12019265, mode3=1)
    else:
        """State 4,13"""
        assert t000001000_x14(text1=10621100, flag8=12019266, mode3=1)
    """State 14"""
    return 0

def t000001000_x56():
    """State 0"""
    if not GetEventFlag(12019275):
        """State 2"""
        assert t000001000_x14(text1=10625000, flag8=12019275, mode3=1)
    else:
        """State 3"""
        assert t000001000_x14(text1=10625100, flag8=12019276, mode3=1)
    """State 1"""
    SetEventFlag(1034509407, FlagState.On)
    """State 4"""
    return 0

def t000001000_x57(z23=11):
    """State 0,7"""
    if not GetEventFlag(4680):
        """State 4"""
        if not GetEventFlag(1042372700):
            """State 2"""
            AddTalkListDataAlt(z23, 21000001, -1, 0, True)
            SetEventFlag(1042379200, FlagState.On)
        elif GetEventFlag(4699):
            """State 31"""
            assert t000001000_x46(z24=z23)
        else:
            """State 5"""
            pass
    else:
        """State 6"""
        if (GetEventFlag(10009655) and not GetEventFlag(105) and not DoesPlayerHaveSpEffect(4270) and not DoesPlayerHaveSpEffect(4271)
            and not DoesPlayerHaveSpEffect(4272) and not DoesPlayerHaveSpEffect(4280) and not DoesPlayerHaveSpEffect(4282)
            and not DoesPlayerHaveSpEffect(4286)):
            """State 18"""
            AddTalkListDataAlt(z23, 21000050, -1, 0, True)
            SetEventFlag(10009656, FlagState.On)
        elif GetEventFlag(1042372701) and not GetEventFlag(1042379203) and not GetEventFlag(10009655):
            """State 3"""
            AddTalkListDataAlt(z23, 21000002, -1, 0, True)
            SetEventFlag(1042379202, FlagState.On)
        elif GetEventFlag(1042372703):
            """State 28"""
            SetEventFlag(1042379208, FlagState.On)
            AddTalkListDataAltIf(not GetEventFlag(1042379209), z23, 21000004, -1, 0, True)
            AddTalkListDataAltIf(GetEventFlag(1042379209), z23, 21000004, -1, 0, False)
        elif (not GetEventFlag(1042372702) and not GetEventFlag(1042379207) and GetEventFlag(1042379203) and not
              GetEventFlag(10009655)):
            """State 8"""
            AddTalkListDataAlt(z23, 21000003, -1, 0, True)
            SetEventFlag(1042379206, FlagState.On)
        elif GetEventFlag(1046382701) and not GetEventFlag(1046389202):
            """State 9"""
            SetEventFlag(1046389201, FlagState.On)
            AddTalkListDataAltIf(not GetEventFlag(1046389203) and not GetEventFlag(1046382700), z23, 21000005,
                                 -1, 0, True)
            AddTalkListDataAltIf(GetEventFlag(1046389203) and not GetEventFlag(1046382700), z23, 21000005, -1,
                                 0, False)
            AddTalkListDataIf(GetEventFlag(1046382700), z23, 21000006, -1)
        elif GetEventFlag(1043342700) and not GetEventFlag(1043349251):
            """State 10"""
            SetEventFlag(1043349250, FlagState.On)
            AddTalkListDataAltIf(not GetEventFlag(1043349252) and not GetEventFlag(1046382700), z23, 21000007,
                                 -1, 0, True)
            AddTalkListDataAltIf(GetEventFlag(1043349252) and not GetEventFlag(1046382700), z23, 21000007, -1,
                                 0, False)
            AddTalkListDataIf(GetEventFlag(1046382700), z23, 21000008, -1)
        elif GetEventFlag(1038502710) and not GetEventFlag(1038509251):
            """State 11"""
            SetEventFlag(1038509250, FlagState.On)
            AddTalkListDataAltIf(not GetEventFlag(1038509252) and not GetEventFlag(1046382700), z23, 21000009,
                                 -1, 0, True)
            AddTalkListDataAltIf(GetEventFlag(1038509252) and not GetEventFlag(1046382700), z23, 21000009, -1,
                                 0, False)
            AddTalkListDataIf(GetEventFlag(1046382700), z23, 21000010, -1)
        elif GetEventFlag(1043532710) and not GetEventFlag(1043539251):
            """State 12"""
            SetEventFlag(1043539250, FlagState.On)
            AddTalkListDataAltIf(not GetEventFlag(1043539252) and not GetEventFlag(1046382700), z23, 21000011,
                                 -1, 0, True)
            AddTalkListDataAltIf(GetEventFlag(1043539252) and not GetEventFlag(1046382700), z23, 21000011, -1,
                                 0, False)
            AddTalkListDataIf(GetEventFlag(1046382700), z23, 21000012, -1)
        elif GetEventFlag(11002740) and not GetEventFlag(11009256):
            """State 13"""
            SetEventFlag(11009255, FlagState.On)
            AddTalkListDataAltIf(not GetEventFlag(11009257) and not GetEventFlag(1046382700), z23, 21000013, -1,
                                 0, True)
            AddTalkListDataAltIf(GetEventFlag(11009257) and not GetEventFlag(1046382700), z23, 21000013, -1, 0,
                                 False)
            AddTalkListDataIf(GetEventFlag(1046382700), z23, 21000014, -1)
        elif GetEventFlag(1043502700) and not GetEventFlag(1043509201):
            """State 25"""
            SetEventFlag(1043509200, FlagState.On)
            AddTalkListDataAltIf(not GetEventFlag(1043509202) and not GetEventFlag(1046382700), z23, 21000015,
                                 -1, 0, True)
            AddTalkListDataAltIf(GetEventFlag(1043509202) and not GetEventFlag(1046382700), z23, 21000015, -1,
                                 0, False)
            AddTalkListDataIf(GetEventFlag(1046382700), z23, 21000016, -1)
        elif GetEventFlag(1054552700) and not GetEventFlag(1054559201):
            """State 14"""
            SetEventFlag(1054559200, FlagState.On)
            AddTalkListDataAltIf(not GetEventFlag(1054559202) and not GetEventFlag(1046382700), z23, 21000017,
                                 -1, 0, True)
            AddTalkListDataAltIf(GetEventFlag(1054559202) and not GetEventFlag(1046382700), z23, 21000017, -1,
                                 0, False)
            AddTalkListDataIf(GetEventFlag(1046382700), z23, 21000018, -1)
        elif (not GetEventFlag(1037519201) and not GetEventFlag(11009260) and not GetEventFlag(400001) and (GetEventFlag(1037512700)
              or GetEventFlag(1038512700) or GetEventFlag(1038502711) or GetEventFlag(1039512711) or GetEventFlag(1037522700))):
            """State 17"""
            AddTalkListDataAlt(z23, 21000022, -1, 0, True)
            SetEventFlag(1037519200, FlagState.On)
        elif GetEventFlag(1036482710) and GetEventFlag(1036489213) and GetEventFlag(3940) and not GetEventFlag(1036489251):
            """State 15"""
            AddTalkListDataAlt(z23, 21000020, -1, 0, True)
            SetEventFlag(1036489250, FlagState.On)
        elif (GetEventFlag(1039512710) and GetEventFlag(1039519209) and GetEventFlag(1036489210) and GetEventFlag(3940)
              and not GetEventFlag(1039519251)):
            """State 16"""
            SetEventFlag(1039519250, FlagState.On)
            AddTalkListDataAlt(z23, 21000021, -1, 0, True)
        elif GetEventFlag(11002745):
            """State 29"""
            AddTalkListDataAltIf(not GetEventFlag(11009266), z23, 21000023, -1, 0, False)
            AddTalkListDataAltIf(GetEventFlag(11009266), z23, 21000023, -1, 0, False)
            SetEventFlag(11009265, FlagState.On)
        elif ((GetEventFlag(1054552701) or GetEventFlag(1052562700) or GetEventFlag(1052542700) or GetEventFlag(1051532700)
              or GetEventFlag(1052532710)) and not GetEventFlag(1054539211)):
            """State 21"""
            SetEventFlag(1054539210, FlagState.On)
            AddTalkListDataAlt(z23, 21000026, -1, 0, True)
        elif GetEventFlag(1054532702):
            """State 22"""
            SetEventFlag(1054539215, FlagState.On)
            AddTalkListDataAltIf(not GetEventFlag(1054539216), z23, 21000027, -1, 0, True)
            AddTalkListDataAltIf(GetEventFlag(1054539216), z23, 21000027, -1, 0, True)
        elif (GetEventFlag(35002730) or GetEventFlag(35002731)) and not GetEventFlag(35009351):
            """State 23"""
            SetEventFlag(35009350, FlagState.On)
            AddTalkListDataAlt(z23, 21000028, -1, 0, True)
        elif GetEventFlag(35002731) and not GetEventFlag(35009353):
            """State 24"""
            SetEventFlag(35009352, FlagState.On)
            AddTalkListDataAlt(z23, 21000030, -1, 0, True)
        elif GetEventFlag(35002732) and not GetEventFlag(35002733):
            """State 26"""
            AddTalkListDataAltIf(not GetEventFlag(35009356) and not GetEventFlag(35009357), z23, 21000029, -1,
                                 0, False)
            AddTalkListDataAltIf(GetEventFlag(35009356) or GetEventFlag(35009357), z23, 21000029, -1, 0, False)
            SetEventFlag(35009355, FlagState.On)
        elif GetEventFlag(35002733):
            """State 27"""
            AddTalkListDataAltIf(not GetEventFlag(35009359), z23, 21000031, -1, 0, False)
            AddTalkListDataAltIf(GetEventFlag(35009359), z23, 21000031, -1, 0, False)
            SetEventFlag(35009358, FlagState.On)
        elif GetEventFlag(11109387) and not GetEventFlag(11009271):
            """State 19"""
            SetEventFlag(11009270, FlagState.On)
            AddTalkListDataAlt(z23, 21000024, -1, 0, True)
        elif GetEventFlag(1049539207) and not GetEventFlag(11009276):
            """State 20"""
            SetEventFlag(11009275, FlagState.On)
            AddTalkListDataAlt(z23, 21000025, -1, 0, True)
        elif GetEventFlag(4699):
            """State 30"""
            assert t000001000_x46(z24=z23)
        else:
            """State 1"""
            pass
    """State 32"""
    return 0

def t000001000_x58(z24=12):
    """State 0,5"""
    if not GetEventFlag(4680):
        """State 2"""
        if GetEventFlag(4699):
            """State 7"""
            assert t000001000_x46(z24=z24)
        else:
            """State 3"""
            pass
    else:
        """State 4"""
        if GetEventFlag(4699):
            """State 6"""
            assert t000001000_x46(z24=z24)
        else:
            """State 1"""
            pass
    """State 8"""
    return 0

def t000001000_x59():
    """State 0"""
    if GetEventFlag(953):
        """State 3,1"""
        SetEventFlag(4653, FlagState.On)
    else:
        """State 2"""
        pass
    """State 4"""
    return 0

def t000001000_x60():
    """State 0"""
    if (GetEventFlag(10000851) and not GetEventFlag(10009655) and not DoesPlayerHaveSpEffect(4270) and not DoesPlayerHaveSpEffect(4271)
        and not DoesPlayerHaveSpEffect(4272) and not DoesPlayerHaveSpEffect(4280) and not DoesPlayerHaveSpEffect(4282)
        and not DoesPlayerHaveSpEffect(4286)):
        """State 2,3"""
        Label('L0')
        SetEventFlag(4653, FlagState.On)
    elif ((GetEventFlag(3062) or GetEventFlag(3063) or GetEventFlag(3064) or GetEventFlag(3065)) and not GetEventFlag(10009655)
          and not DoesPlayerHaveSpEffect(4270) and not DoesPlayerHaveSpEffect(4271) and not DoesPlayerHaveSpEffect(4272)
          and not DoesPlayerHaveSpEffect(4280) and not DoesPlayerHaveSpEffect(4282) and not DoesPlayerHaveSpEffect(4286)):
        """State 4"""
        Goto('L0')
    elif (not GetEventFlag(11009260) and not GetEventFlag(400001) and not GetEventFlag(9104) and (GetEventFlag(11002741)
          or GetEventFlag(11002742) or GetEventFlag(11002743) or GetEventFlag(11002744))):
        """State 5"""
        Goto('L0')
    elif GetEventFlag(9104) and not GetEventFlag(400001):
        """State 6"""
        Goto('L0')
    else:
        """State 1"""
        pass
    """State 7"""
    return 0

def t000001000_x61():
    """State 0"""
    if GetEventFlag(9104) and not GetEventFlag(400001):
        """State 2,1"""
        SetEventFlag(4653, FlagState.On)
    else:
        """State 3"""
        pass
    """State 4"""
    return 0

def t000001000_x62():
    """State 0"""
    if not GetEventFlag(35009360):
        """State 3,1"""
        SetEventFlag(4653, FlagState.On)
    else:
        """State 2"""
        pass
    """State 4"""
    return 0

def t000001000_x63():
    """State 0"""
    while True:
        """State 1"""
        if CompareBonfireLevel(CompareType.Equal, 0):
            """State 2"""
            assert t000001000_x5(actionbutton5=6100, flag9=6001, flag10=6000)
        else:
            """State 3"""
            assert t000001000_x3(actionbutton1=6101, flag11=6001, flag12=6000)
        """State 4"""
        assert t000001000_x4(action1=20011020)
    """Unused"""
    """State 5"""
    return 0

def t000001000_x64():
    """State 0,2"""
    if GetCurrentStateElapsedTime() > 0.8:
        """State 3"""
        GiveSpEffectToPlayer(9606)
        def WhilePaused():
            GiveSpEffectToPlayer(9606)
        def ExitPause():
            GiveSpEffectToPlayer(9606)
        if IsTimePassFadeOutInProgress() == False:
            pass
        elif GetEventFlag(9001):
            """State 1"""
            Label('L0')
    elif GetEventFlag(9001):
        Goto('L0')
    """State 4"""
    return 0

def t000001000_x65(actionbutton1=6100, actionbutton2=6101, val2=45, z22=-120):
    """State 0"""
    if RelativeAngleBetweenTwoPlayersWithAxis(z22) < val2:
        """State 1"""
        Label('L0')
        """State 3"""
        call = t000001000_x41(actionbutton1=actionbutton1, actionbutton2=actionbutton2)
        if call.Done():
            """State 4"""
            return 0
        elif not RelativeAngleBetweenTwoPlayersWithAxis(z22) < val2:
            pass
    else:
        pass
    """State 2"""
    assert RelativeAngleBetweenTwoPlayersWithAxis(z22) < val2
    Goto('L0')

def t000001000_x66():
    """State 0,2"""
    if GetCurrentStateElapsedTime() > 0.8:
        """State 3"""
        GiveSpEffectToPlayer(9610)
        def WhilePaused():
            GiveSpEffectToPlayer(9610)
        def ExitPause():
            GiveSpEffectToPlayer(9610)
        if IsTimePassFadeOutInProgress() == False:
            pass
        elif GetEventFlag(9001):
            """State 1"""
            Label('L0')
    elif GetEventFlag(9001):
        Goto('L0')
    """State 4"""
    return 0

def t000001000_x67():
    """State 0"""
    if GetEventFlag(400001) and not GetEventFlag(108) and not GetEventFlag(11002745):
        """State 1,3"""
        assert t000001000_x29(z31=20011)
    else:
        """State 2,4"""
        assert t000001000_x29(z31=20010)
    """State 5"""
    return 0

def t000001000_x68():
    """State 0"""
    if GetEventFlag(1054532702):
        """State 1"""
        if GetEventFlag(110) and not GetEventFlag(1054532703) and not GetEventFlag(9116):
            """State 3,7"""
            SetEventFlag(9000, FlagState.Off)
            SetEventFlag(9020, FlagState.Off)
            """State 6"""
            ChangeCamera(-1)
            """State 5"""
            SetEventFlag(1054539206, FlagState.On)
            assert GetCurrentStateElapsedTime() > 15
            """State 8"""
            ChangeCameraIf(not GetEventFlag(11102790), 1001000)
            SetEventFlag(9000, FlagState.On)
            SetEventFlag(9020, FlagState.On)
            SetEventFlag(1054539206, FlagState.Off)
        else:
            """State 4"""
            pass
    else:
        """State 2"""
        pass
    """State 9"""
    return 0

def t000001000_x69(z21=1, action9=15000370):
    """State 0,5"""
    SetWorkValue(1, GetEstusAllocation(EstusType.HP) + GetEstusAllocation(EstusType.FP) + -4)
    """State 6"""
    assert t000001000_x21(z32=1, z33=1, z34=2, z35=2, z36=3, z37=3, z38=4, z39=4, z40=5, z41=5, z42=1)
    """State 3"""
    if (ComparePlayerInventoryNumber(ItemType.Goods, 10010, CompareType.GreaterOrEqual, GetWorkValue(1), False)
        and GetEstusAllocation(EstusType.HP) + GetEstusAllocation(EstusType.FP) < 13):
        """State 1"""
        AddTalkListDataAlt(z21, action9, -1, 0, True)
    else:
        """State 2"""
        AddTalkListDataAlt(z21, action9, -1, 0, False)
    """State 4"""
    SetWorkValue(1, 0)
    """State 7"""
    return 0

def t000001000_x70(z20=2, action8=15000380):
    """State 0,3"""
    if (ComparePlayerInventoryNumber(ItemType.Goods, 10020, CompareType.GreaterOrEqual, 1, False) and GetTotalBonfireLevel()
        <= 13):
        """State 1"""
        AddTalkListDataAlt(z20, action8, -1, 0, True)
    else:
        """State 2"""
        AddTalkListDataAlt(z20, action8, -1, 0, False)
    """State 4"""
    return 0

def t000001000_x71(z19=3, action7=15000371):
    """State 0,4"""
    SetWorkValue(1, GetEstusAllocation(EstusType.HP) + GetEstusAllocation(EstusType.FP) + -4)
    """State 7"""
    assert t000001000_x21(z32=1, z33=1, z34=2, z35=2, z36=3, z37=3, z38=4, z39=4, z40=5, z41=5, z42=1)
    """State 3"""
    if (ComparePlayerInventoryNumber(ItemType.Goods, 10010, CompareType.NotEqual, GetWorkValue(1), False) or not
        GetEstusAllocation(EstusType.HP) + GetEstusAllocation(EstusType.FP) < 13):
        """State 2"""
        if (ComparePlayerInventoryNumber(ItemType.Goods, 10020, CompareType.Less, 0, False) or not GetTotalBonfireLevel()
            <= 13):
            """State 5"""
            AddTalkListDataAlt(z19, action7, -1, 0, False)
        else:
            """State 1"""
            Label('L0')
            AddTalkListDataAlt(z19, action7, -1, 0, True)
    else:
        Goto('L0')
    """State 6"""
    SetWorkValue(1, 0)
    """State 8"""
    return 0

def t000001000_x72():
    """State 0,1"""
    SetEventFlag(4820, FlagState.Off)
    SetEventFlag(4821, FlagState.Off)
    SetEventFlag(4822, FlagState.Off)
    """State 2"""
    SetEventFlag(4825, FlagState.Off)
    SetEventFlag(4826, FlagState.Off)
    SetEventFlag(4827, FlagState.Off)
    """State 3"""
    return 0

def t000001000_x73(flag4=_, flag5=_, flag6=_):
    """State 0,1"""
    SetEventFlag(flag4, FlagState.On)
    """State 2"""
    SetEventFlag(flag5, FlagState.Off)
    SetEventFlag(flag6, FlagState.Off)
    """State 3"""
    return 0

def t000001000_x74(val1=_):
    """State 0,1"""
    if val1 == 0:
        """State 2,18"""
        assert t000001000_x73(flag4=4825, flag5=4826, flag6=4827)
        """State 5"""
        if IsTimeOfDayInRange(6, 0, 0, 11, 59, 59):
            """State 6,21"""
            Label('L0')
            assert t000001000_x73(flag4=4822, flag5=4820, flag6=4821)
        elif IsTimeOfDayInRange(12, 0, 0, 19, 59, 59):
            """State 7,22"""
            Label('L1')
            assert t000001000_x73(flag4=4821, flag5=4820, flag6=4822)
        elif IsTimeOfDayInRange(20, 0, 0, 5, 59, 59):
            """State 8,23"""
            Label('L2')
            assert t000001000_x73(flag4=4820, flag5=4821, flag6=4822)
        else:
            """State 9"""
            Label('L3')
    elif val1 == 1:
        """State 3,19"""
        assert t000001000_x73(flag4=4826, flag5=4825, flag6=4827)
        """State 10"""
        if IsTimeOfDayInRange(6, 0, 0, 11, 59, 59):
            """State 11"""
            Goto('L2')
        elif IsTimeOfDayInRange(12, 0, 0, 19, 59, 59):
            """State 12"""
            Goto('L0')
        elif IsTimeOfDayInRange(20, 0, 0, 5, 59, 59):
            """State 13"""
            Goto('L1')
        else:
            Goto('L3')
    elif val1 == 2:
        """State 4,20"""
        assert t000001000_x73(flag4=4827, flag5=4825, flag6=4826)
        """State 14"""
        if IsTimeOfDayInRange(6, 0, 0, 11, 59, 59):
            """State 15"""
            Goto('L1')
        elif IsTimeOfDayInRange(12, 0, 0, 19, 59, 59):
            """State 16"""
            Goto('L2')
        elif IsTimeOfDayInRange(20, 0, 0, 5, 59, 59):
            """State 17"""
            Goto('L0')
        else:
            Goto('L3')
    else:
        Goto('L3')
    """State 24"""
    return 0

def t000001000_x75(goods4=2010000):
    """State 0,1"""
    if GetEventFlag(720300):
        """State 2"""
        pass
    else:
        """State 3,5"""
        SetEventFlag(720300, FlagState.On)
    """State 6,4"""
    if GetScadutreeLevel() <= 20:
        """State 7,21"""
        assert t000001000_x81(z4=1, z5=2, z6=3, z7=2)
        """State 18"""
        call = t000001000_x0(action10=20011039 + GetWorkValue(2))
        if call.Get() == 0:
            """State 9,11"""
            if (ComparePlayerInventoryNumber(ItemType.Goods, goods4, CompareType.GreaterOrEqual, GetWorkValue(2),
                False)):
                """State 12,13"""
                PlayerEquipmentQuantityChange(ItemType.Goods, goods4, GetWorkValue(2) * -1)
                """State 15"""
                SetScadutreeLevel(GetScadutreeLevel() + 1)
                """State 20"""
                assert t000001000_x4(action1=20011062)
                """State 16"""
                SetWorkValue(2, 0)
            else:
                """State 14,19"""
                assert t000001000_x4(action1=20011060)
        elif call.Done():
            """State 10"""
            pass
    else:
        """State 8,17"""
        assert t000001000_x4(action1=20011064)
    """State 22"""
    return 0

def t000001000_x76(goods5=2010100):
    """State 0,1"""
    if GetEventFlag(720310):
        """State 2"""
        pass
    else:
        """State 3,4"""
        SetEventFlag(720310, FlagState.On)
    """State 5,6"""
    if GetReveredSpiritAshLevel() <= 10:
        """State 7,18"""
        assert t000001000_x77(z8=1, z9=1, z10=1, z11=2, z12=2, z13=3, z14=3, z15=3, z16=4, z17=5, z18=2, mode1=1)
        """State 19"""
        call = t000001000_x0(action10=20011049 + GetWorkValue(2))
        if call.Get() == 0:
            """State 9,11"""
            if (ComparePlayerInventoryNumber(ItemType.Goods, goods5, CompareType.GreaterOrEqual, GetWorkValue(2),
                False)):
                """State 12,13"""
                PlayerEquipmentQuantityChange(ItemType.Goods, goods5, GetWorkValue(2) * -1)
                """State 15"""
                SetReveredSpiritAshLevel(GetReveredSpiritAshLevel() + 1)
                """State 21"""
                assert t000001000_x4(action1=20011063)
                """State 16"""
                SetWorkValue(2, 0)
            else:
                """State 14,20"""
                assert t000001000_x4(action1=20011061)
        elif call.Done():
            """State 10"""
            pass
    else:
        """State 8,17"""
        assert t000001000_x4(action1=20011065)
    """State 22"""
    return 0

def t000001000_x77(z8=1, z9=1, z10=1, z11=2, z12=2, z13=3, z14=3, z15=3, z16=4, z17=5, z18=2, mode1=_):
    """State 0,13"""
    SetWorkValue(z18, 0)
    """State 14"""
    if mode1 == 0:
        """State 15,16"""
        SetWorkValue(z18, GetScadutreeLevel())
    else:
        """State 17,18"""
        SetWorkValue(z18, GetReveredSpiritAshLevel())
    """State 19,1"""
    if GetWorkValue(z18) == 0:
        """State 2"""
        SetWorkValue(z18, z8)
    elif GetWorkValue(z18) == 1:
        """State 3"""
        SetWorkValue(z18, z9)
    elif GetWorkValue(z18) == 2:
        """State 4"""
        SetWorkValue(z18, z10)
    elif GetWorkValue(z18) == 3:
        """State 5"""
        SetWorkValue(z18, z11)
    elif GetWorkValue(z18) == 4:
        """State 6"""
        SetWorkValue(z18, z12)
    elif GetWorkValue(z18) == 5:
        """State 7"""
        SetWorkValue(z18, z13)
    elif GetWorkValue(z18) == 6:
        """State 8"""
        SetWorkValue(z18, z14)
    elif GetWorkValue(z18) == 7:
        """State 9"""
        SetWorkValue(z18, z15)
    elif GetWorkValue(z18) == 8:
        """State 10"""
        SetWorkValue(z18, z16)
    elif GetWorkValue(z18) == 9:
        """State 11"""
        SetWorkValue(z18, z17)
    else:
        """State 12"""
        SetWorkValue(z18, 999)
    """State 20"""
    return 0

def t000001000_x78(goods4=2010000, goods5=2010100):
    """State 0,2"""
    CloseShopMessage()
    while True:
        """State 1"""
        ClearTalkListData()
        """State 3,8"""
        assert t000001000_x79(z3=1, action6=20010002, mode1=0, goods4=goods4)
        """State 9"""
        assert t000001000_x79(z3=2, action6=20010003, mode1=1, goods4=goods5)
        """State 4"""
        AddTalkListData(99, 20010004, -1)
        """State 5"""
        ShowShopMessage(TalkOptionsType.Regular)
        assert not (CheckSpecificPersonMenuIsOpen(1, 0) and not CheckSpecificPersonGenericDialogIsOpen(0))
        """State 6"""
        if GetTalkListEntryResult() == 1:
            """State 10"""
            assert t000001000_x75(goods4=goods4)
        elif GetTalkListEntryResult() == 2:
            """State 11"""
            assert t000001000_x76(goods5=goods5)
        else:
            """State 7,12"""
            return 0

def t000001000_x79(z3=_, action6=_, mode1=_, goods4=_):
    """State 0,4,5"""
    if mode1 == 0:
        """State 6,8"""
        if GetScadutreeLevel() <= 20:
            """State 9,17"""
            assert t000001000_x81(z4=1, z5=2, z6=3, z7=2)
            """State 1"""
            Label('L0')
            if (ComparePlayerInventoryNumber(ItemType.Goods, goods4, CompareType.GreaterOrEqual, GetWorkValue(2),
                False)):
                """State 2,12"""
                AddTalkListDataAlt(z3, action6, -1, 0, True)
            else:
                """State 3,13"""
                Label('L1')
                AddTalkListDataAlt(z3, action6, -1, 0, False)
        else:
            """State 10"""
            Label('L2')
            Goto('L1')
    else:
        """State 7,11"""
        if GetReveredSpiritAshLevel() <= 10:
            """State 15,16"""
            assert t000001000_x77(z8=1, z9=1, z10=1, z11=2, z12=2, z13=3, z14=3, z15=3, z16=4, z17=5, z18=2, mode1=mode1)
            Goto('L0')
        else:
            Goto('L2')
    """State 14"""
    SetWorkValue(2, 0)
    """State 18"""
    return 0

def t000001000_x80(z2=50, action5=20010001, goods2=2010000, goods3=2010100):
    """State 0,1,2"""
    if GetEntityID() > 20000000 and GetEntityID() < 28999999:
        """State 3"""
        Label('L0')
        """State 7,16"""
        assert t000001000_x81(z4=1, z5=2, z6=3, z7=2)
        """State 8"""
        if ComparePlayerInventoryNumber(ItemType.Goods, goods2, CompareType.NotEqual, GetWorkValue(2), False):
            """State 9,15"""
            assert t000001000_x77(z8=1, z9=1, z10=1, z11=2, z12=2, z13=3, z14=3, z15=3, z16=4, z17=5, z18=2, mode1=1)
            """State 10"""
            if ComparePlayerInventoryNumber(ItemType.Goods, goods3, CompareType.NotEqual, GetWorkValue(2), False):
                """State 12"""
                AddTalkListDataAlt(z2, action5, -1, 0, False)
            else:
                """State 13"""
                Label('L1')
                """State 11"""
                AddTalkListDataAlt(z2, action5, -1, 0, True)
        else:
            Goto('L1')
        """State 14"""
        SetWorkValue(2, 0)
    else:
        """State 4"""
        if GetEntityID() > 40000000 and GetEntityID() < 43999999:
            Goto('L0')
        else:
            """State 5"""
            if GetEntityID() > 2000000000 and GetEntityID() < 2099999999:
                Goto('L0')
            else:
                """State 6"""
                pass
    """State 17"""
    return 0

def t000001000_x81(z4=1, z5=2, z6=3, z7=2):
    """State 0,6"""
    SetWorkValue(z7, 0)
    """State 7,8"""
    SetWorkValue(z7, GetScadutreeLevel())
    """State 9,1"""
    if GetWorkValue(z7) <= 1:
        """State 2"""
        SetWorkValue(z7, z4)
    elif GetWorkValue(z7) <= 9:
        """State 3"""
        SetWorkValue(z7, z5)
    elif GetWorkValue(z7) <= 20:
        """State 4"""
        SetWorkValue(z7, z6)
    else:
        """State 5"""
        SetWorkValue(z7, 999)
    """State 10"""
    return 0

def t000001000_x82():
    """State 0,5"""
    SetEventFlag(4828, FlagState.Off)
    SetEventFlag(4829, FlagState.Off)
    SetEventFlag(4830, FlagState.Off)
    """State 1"""
    if GetEntityID() > 2045420950 and GetEntityID() < 2045420950:
        """State 2,3"""
        SetEventFlag(4828, FlagState.On)
        """State 8"""
        SetEventFlag(4830, FlagState.On)
    elif GetEntityID() > 21010953 and GetEntityID() < 21010953:
        """State 6,7"""
        SetEventFlag(4829, FlagState.On)
    else:
        """State 4"""
        pass
    """State 9"""
    return 0

def t000001000_x83():
    """State 0,1"""
    if GetEntityID() > 2048420950 and GetEntityID() < 2048420950:
        """State 2,3"""
        SetEventFlag(2048422709, FlagState.On)
    elif GetEntityID() > 21010953 and GetEntityID() < 21010953:
        """State 4,6"""
        SetEventFlag(21012732, FlagState.On)
    elif GetEntityID() > 2049390950 and GetEntityID() < 2049390950:
        """State 7,8"""
        SetEventFlag(2049392710, FlagState.On)
    else:
        """State 5"""
        pass
    """State 9"""
    return 0

def t000001000_x84():
    """State 0,1"""
    if ((GetEntityID() > 20000000 and GetEntityID() < 28999999) or (GetEntityID() > 40000000 and GetEntityID()
        < 43999999) or (GetEntityID() > 2000000000 and GetEntityID() < 2099999999)):
        """State 2,4"""
        return 0
    else:
        """State 3,5"""
        return 1

def t000001000_x85():
    """State 0,2"""
    if GetEventFlag(69560):
        """State 3,1"""
        Label('L0')
        AddTalkListData(75, 20010070, -1)
    else:
        """State 4,5"""
        if (ComparePlayerInventoryNumber(ItemType.Goods, 2009600, CompareType.GreaterOrEqual, 1, False) or ComparePlayerInventoryNumber(ItemType.Goods,
            2009610, CompareType.GreaterOrEqual, 1, False) or ComparePlayerInventoryNumber(ItemType.Goods, 2009620,
            CompareType.GreaterOrEqual, 1, False)):
            """State 6,8"""
            SetEventFlag(69560, FlagState.On)
            """State 9"""
            assert t000001000_x86()
            Goto('L0')
        else:
            """State 7"""
            pass
    """State 10"""
    return 0

def t000001000_x86():
    """State 0,1"""
    assert GetCurrentStateElapsedTime() > 0.5
    """State 2"""
    assert t000001000_x4(action1=20011070)
    """State 3"""
    return 0

def t000001000_x87():
    """State 0,1"""
    CloseShopMessage()
    while True:
        """State 2"""
        ClearTalkListData()
        """State 11"""
        assert t000001000_x89(flag2=6700)
        """State 12"""
        assert t000001000_x88(goods1=2009600, flag3=6701, z1=2, action3=20010076, action4=20010072)
        """State 13"""
        assert t000001000_x88(goods1=2009610, flag3=6702, z1=3, action3=20010077, action4=20010073)
        """State 14"""
        assert t000001000_x88(goods1=2009620, flag3=6703, z1=4, action3=20010078, action4=20010074)
        """State 3"""
        AddTalkListData(99, 20010079, -1)
        """State 4"""
        ShowShopMessage(TalkOptionsType.Regular)
        assert not (CheckSpecificPersonMenuIsOpen(1, 0) and not CheckSpecificPersonGenericDialogIsOpen(0))
        """State 5"""
        if GetTalkListEntryResult() == 1:
            """State 6,15"""
            assert t000001000_x90(flag1=6700, action1=20011075, action2=20011071)
        elif GetTalkListEntryResult() == 2:
            """State 7,16"""
            assert t000001000_x90(flag1=6701, action1=20011076, action2=20011072)
        elif GetTalkListEntryResult() == 3:
            """State 8,17"""
            assert t000001000_x90(flag1=6702, action1=20011077, action2=20011073)
        elif GetTalkListEntryResult() == 4:
            """State 9,18"""
            assert t000001000_x90(flag1=6703, action1=20011078, action2=20011074)
        else:
            """State 10,19"""
            return 0

def t000001000_x88(goods1=_, flag3=_, z1=_, action3=_, action4=_):
    """State 0,6"""
    if ComparePlayerInventoryNumber(ItemType.Goods, goods1, CompareType.GreaterOrEqual, 1, False):
        """State 7,1"""
        if GetEventFlag(flag3):
            """State 2,3"""
            AddTalkListData(z1, action3, -1)
        else:
            """State 4,5"""
            AddTalkListData(z1, action4, -1)
    else:
        """State 8"""
        pass
    """State 9"""
    return 0

def t000001000_x89(flag2=6700):
    """State 0,1"""
    if GetEventFlag(flag2):
        """State 4,3"""
        AddTalkListData(1, 20010075, -1)
    else:
        """State 5,2"""
        AddTalkListData(1, 20010071, -1)
    """State 6"""
    return 0

def t000001000_x90(flag1=_, action1=_, action2=_):
    """State 0,1"""
    if GetEventFlag(flag1):
        """State 2,6"""
        assert t000001000_x4(action1=action1)
    else:
        """State 3,5"""
        SetEventFlag(6700, FlagState.Off)
        SetEventFlag(6701, FlagState.Off)
        SetEventFlag(6702, FlagState.Off)
        SetEventFlag(6703, FlagState.Off)
        """State 4"""
        SetEventFlag(flag1, FlagState.On)
        """State 7"""
        assert t000001000_x4(action1=action2)
    """State 8"""
    return 0

