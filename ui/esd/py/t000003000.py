# -*- coding: utf-8 -*-
def t000003000_1():
    """State 0,1"""
    if not IsClientPlayer():
        """State 3"""
        Label('L0')
        call = t000003000_x46()
        def WhilePaused():
            GiveSpEffectToSelfIf(not GetEventFlag(400001) or GetEventFlag(108), 9600)
            GiveSpEffectToSelfIf(GetEventFlag(400001) and not GetEventFlag(108), 9601)
            GiveSpEffectToPlayerIf(GetRelativeAngleToPlayerWithAxis(90) < 90, 9600)
            GiveSpEffectToPlayerIf(not GetRelativeAngleToPlayerWithAxis(90) < 90, 9603)
        assert IsClientPlayer()
    else:
        pass
    """State 4"""
    call = t000003000_x47()
    assert not IsClientPlayer()
    Goto('L0')
    """Unused"""
    """State 2"""
    t000003000_x7(flag3=6000, flag4=6000, flag5=6000, val1=5, val2=10, val3=12, val4=10, val5=12, actionbutton1=6000,
                  flag6=6001, flag7=6000, flag8=4652, flag9=6000, flag10=6000, z1=1, z2=1000000, z3=1000000, z4=1000000,
                  mode2=1, mode3=1)
    Quit()

def t000003000_x0(actionbutton1=6000, flag7=6000, flag11=6000, flag12=6000, flag13=6000, flag14=6000, flag6=6001):
    """State 0"""
    while True:
        """State 1"""
        assert not GetOneLineHelpStatus() and not IsClientPlayer() and not IsPlayerDead() and not IsCharacterDisabled()
        """State 3"""
        assert (GetEventFlag(flag7) or GetEventFlag(flag11) or GetEventFlag(flag12) or GetEventFlag(flag13) or
                GetEventFlag(flag14))
        """State 4"""
        assert not GetEventFlag(flag6)
        """State 2"""
        if (GetEventFlag(flag6) or not (not GetOneLineHelpStatus() and not IsClientPlayer() and not IsPlayerDead()
            and not IsCharacterDisabled()) or (not GetEventFlag(flag7) and not GetEventFlag(flag11) and not GetEventFlag(flag12)
            and not GetEventFlag(flag13) and not GetEventFlag(flag14))):
            pass
        elif CheckActionButtonArea(actionbutton1):
            break
    """State 5"""
    return 0

def t000003000_x1():
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

def t000003000_x2():
    """State 0,1"""
    ClearTalkProgressData()
    StopEventAnimWithoutForcingConversationEnd(0)
    ForceCloseGenericDialog()
    ForceCloseMenu()
    ReportConversationEndToHavokBehavior()
    """State 2"""
    return 0

def t000003000_x3(lot1=_):
    """State 0,1"""
    AwardItemLot(lot1)
    assert not IsMenuOpen(MenuType.Bonfire) and GetCurrentStateElapsedFrames() > 1
    """State 2"""
    return 0

def t000003000_x4(action1=23241004):
    """State 0,1"""
    OpenGenericDialog(DialogBoxType.CenterBottom1, action1, DialogResult.Left, DialogBoxStyle.OrnateNoOptions, 1)
    assert not CheckSpecificPersonGenericDialogIsOpen(0)
    """State 2"""
    return 0

def t000003000_x5(val2=10, val3=12):
    """State 0,1"""
    assert GetDistanceToPlayer() < val2 and GetCurrentStateElapsedFrames() > 1
    """State 2"""
    if PlayerDiedFromFallInstantly() == False and PlayerDiedFromFallDamage() == False:
        """State 3,6"""
        call = t000003000_x21()
        if call.Done():
            pass
        elif GetDistanceToPlayer() > val3 or GetTalkInterruptReason() == 6:
            """State 5"""
            assert t000003000_x1()
    else:
        """State 4,7"""
        call = t000003000_x35()
        if call.Done():
            pass
        elif GetDistanceToPlayer() > val3 or GetTalkInterruptReason() == 6:
            """State 8"""
            assert t000003000_x1()
    """State 9"""
    return 0

def t000003000_x6():
    """State 0,1"""
    assert t000003000_x1()
    """State 2"""
    return 0

def t000003000_x7(flag3=6000, flag4=6000, flag5=6000, val1=5, val2=10, val3=12, val4=10, val5=12, actionbutton1=6000,
                  flag6=6001, flag7=6000, flag8=4652, flag9=6000, flag10=6000, z1=1, z2=1000000, z3=1000000, z4=1000000,
                  mode2=1, mode3=1):
    """State 0"""
    assert GetCurrentStateElapsedTime() > 1.5
    while True:
        """State 2"""
        call = t000003000_x24(flag3=flag3, flag4=flag4, flag5=flag5, val1=val1, val2=val2, val3=val3, val4=val4,
                              val5=val5, actionbutton1=actionbutton1, flag6=flag6, flag7=flag7, flag8=flag8, flag9=flag9,
                              flag10=flag10, z1=z1, z2=z2, z3=z3, z4=z4, mode2=mode2, mode3=mode3)
        assert IsClientPlayer()
        """State 1"""
        call = t000003000_x23()
        assert not IsClientPlayer()
    """Unused"""
    """State 3"""
    return 0

def t000003000_x8(val1=5, val2=10, val3=12, val4=10, val5=12, actionbutton1=6000, flag6=6001, flag7=6000, flag8=4652,
                  flag9=6000, flag10=6000, z1=1, z2=1000000, z3=1000000, z4=1000000, mode2=1, mode3=1):
    """State 0"""
    while True:
        """State 2"""
        call = t000003000_x11(actionbutton1=actionbutton1, flag6=flag6, flag7=flag7, z2=z2, z3=z3, z4=z4)
        def WhilePaused():
            RemoveMyAggroIf(IsAttackedBySomeone() and (DoesSelfHaveSpEffect(9626) and DoesSelfHaveSpEffect(9627)))
            GiveSpEffectToPlayerIf(not CheckSpecificPersonTalkHasEnded(0), 9640)
        if call.Done():
            """State 4"""
            Label('L0')
            ChangeCamera(1000000)
            call = t000003000_x15(val1=val1, z1=z1)
            def WhilePaused():
                ChangeCameraIf(GetDistanceToPlayer() > 2.5, -1)
                RemoveMyAggroIf(IsAttackedBySomeone() and (DoesSelfHaveSpEffect(9626) and DoesSelfHaveSpEffect(9627)))
                GiveSpEffectToPlayer(9640)
                SetLookAtEntityForTalkIf(mode2 == 1, -1, 0)
                SetLookAtEntityForTalkIf(mode3 == 1, 0, -1)
            def ExitPause():
                ChangeCamera(-1)
            if call.Done():
                continue
            elif IsAttackedBySomeone():
                pass
        elif IsAttackedBySomeone() and not DoesSelfHaveSpEffect(9626) and not DoesSelfHaveSpEffect(9627):
            pass
        elif GetEventFlag(flag10):
            Goto('L0')
        elif GetEventFlag(flag8) and not GetEventFlag(flag9) and GetDistanceToPlayer() < val4:
            """State 5"""
            call = t000003000_x17(val5=val5)
            if call.Done():
                continue
            elif IsAttackedBySomeone():
                pass
        elif ((GetDistanceToPlayer() > val5 or GetTalkInterruptReason() == 6) and not CheckSpecificPersonTalkHasEnded(0)
              and not DoesSelfHaveSpEffect(9625)):
            """State 6"""
            assert t000003000_x28() and CheckSpecificPersonTalkHasEnded(0)
            continue
        elif GetEventFlag(9000):
            """State 1"""
            assert not GetEventFlag(9000)
            continue
        """State 3"""
        def ExitPause():
            RemoveMyAggro()
        assert t000003000_x13(val2=val2, val3=val3)
    """Unused"""
    """State 7"""
    return 0

def t000003000_x9(val2=10, val3=12):
    """State 0,1"""
    call = t000003000_x19(val2=val2, val3=val3)
    assert IsPlayerDead()
    """State 2"""
    t000003000_x5(val2=val2, val3=val3)
    Quit()
    """Unused"""
    """State 3"""
    return 0

def t000003000_x10(flag3=6000, val2=10, val3=12):
    """State 0,8"""
    assert t000003000_x37()
    """State 1"""
    if GetEventFlag(flag3):
        """State 2"""
        pass
    else:
        """State 3"""
        if GetDistanceToPlayer() < val2:
            """State 4,6"""
            call = t000003000_x22()
            if call.Done():
                pass
            elif GetDistanceToPlayer() > val3 or GetTalkInterruptReason() == 6:
                """State 7"""
                assert t000003000_x1()
        else:
            """State 5"""
            pass
    """State 9"""
    return 0

def t000003000_x11(actionbutton1=6000, flag6=6001, flag7=6000, z2=1000000, z3=1000000, z4=1000000):
    """State 0,1"""
    call = t000003000_x12(machine1=2000, val6=2000)
    if call.Get() == 1:
        """State 2"""
        assert (t000003000_x0(actionbutton1=actionbutton1, flag7=flag7, flag11=6000, flag12=6000, flag13=6000,
                flag14=6000, flag6=flag6))
    elif call.Done():
        pass
    """State 3"""
    return 0

def t000003000_x12(machine1=_, val6=_):
    """State 0,1"""
    if MachineExists(machine1):
        """State 2"""
        assert GetCurrentStateElapsedFrames() > 1
        """State 4"""
        def WhilePaused():
            RunMachine(machine1)
        assert GetMachineResult() == val6
        """State 5"""
        return 0
    else:
        """State 3,6"""
        return 1

def t000003000_x13(val2=10, val3=12):
    """State 0"""
    assert GetCurrentStateElapsedFrames() > 1
    """State 5"""
    assert t000003000_x1()
    """State 3"""
    if GetDistanceToPlayer() < val2:
        """State 1"""
        if IsPlayerAttacking():
            """State 6"""
            call = t000003000_x14()
            if call.Done():
                pass
            elif GetDistanceToPlayer() > val3 or GetTalkInterruptReason() == 6:
                """State 7"""
                assert t000003000_x29()
        else:
            """State 4"""
            pass
    else:
        """State 2"""
        pass
    """State 8"""
    return 0

def t000003000_x14():
    """State 0,1"""
    assert t000003000_x12(machine1=1101, val6=1101)
    """State 2"""
    return 0

def t000003000_x15(val1=5, z1=1):
    """State 0,2"""
    assert t000003000_x25()
    """State 1"""
    call = t000003000_x16()
    if call.Done():
        pass
    elif (GetDistanceToPlayer() > val1 or GetTalkInterruptReason() == 6) and not DoesSelfHaveSpEffect(9625):
        """State 3"""
        assert t000003000_x27()
    """State 4"""
    return 0

def t000003000_x16():
    """State 0,1"""
    assert t000003000_x12(machine1=1000, val6=1000)
    """State 2"""
    return 0

def t000003000_x17(val5=12):
    """State 0,1"""
    call = t000003000_x18()
    if call.Done():
        pass
    elif GetDistanceToPlayer() > val5 or GetTalkInterruptReason() == 6:
        """State 2"""
        assert t000003000_x28()
    """State 3"""
    return 0

def t000003000_x18():
    """State 0,1"""
    assert t000003000_x12(machine1=1100, val6=1100)
    """State 2"""
    return 0

def t000003000_x19(val2=10, val3=12):
    """State 0,5"""
    assert t000003000_x37()
    """State 2"""
    assert not GetEventFlag(3000)
    while True:
        """State 1"""
        assert GetDistanceToPlayer() < val2
        """State 3"""
        call = t000003000_x20()
        if call.Done():
            pass
        elif GetDistanceToPlayer() > val3 or GetTalkInterruptReason() == 6:
            """State 4"""
            assert t000003000_x30()
    """Unused"""
    """State 6"""
    return 0

def t000003000_x20():
    """State 0,2"""
    call = t000003000_x12(machine1=1102, val6=1102)
    if call.Get() == 1:
        """State 1"""
        Quit()
    elif call.Done():
        """State 3"""
        return 0

def t000003000_x21():
    """State 0,1"""
    assert t000003000_x12(machine1=1001, val6=1001)
    """State 2"""
    return 0

def t000003000_x22():
    """State 0,1"""
    assert t000003000_x12(machine1=1103, val6=1103)
    """State 2"""
    return 0

def t000003000_x23():
    """State 0"""
    Quit()
    """Unused"""
    """State 1"""
    return 0

def t000003000_x24(flag3=6000, flag4=6000, flag5=6000, val1=5, val2=10, val3=12, val4=10, val5=12, actionbutton1=6000,
                   flag6=6001, flag7=6000, flag8=4652, flag9=6000, flag10=6000, z1=1, z2=1000000, z3=1000000, z4=1000000,
                   mode2=1, mode3=1):
    """State 0"""
    while True:
        """State 1"""
        RemoveMyAggro()
        call = t000003000_x8(val1=val1, val2=val2, val3=val3, val4=val4, val5=val5, actionbutton1=actionbutton1,
                             flag6=flag6, flag7=flag7, flag8=flag8, flag9=flag9, flag10=flag10, z1=z1, z2=z2, z3=z3,
                             z4=z4, mode2=mode2, mode3=mode3)
        if CheckSelfDeath() or GetEventFlag(flag3):
            """State 3"""
            Label('L0')
            call = t000003000_x10(flag3=flag3, val2=val2, val3=val3)
            if not CheckSelfDeath() and not GetEventFlag(flag3):
                continue
            elif GetEventFlag(9000):
                pass
        elif GetEventFlag(flag4) or GetEventFlag(flag5):
            """State 2"""
            call = t000003000_x9(val2=val2, val3=val3)
            if CheckSelfDeath() or GetEventFlag(flag3):
                Goto('L0')
            elif not GetEventFlag(flag4) and not GetEventFlag(flag5):
                continue
            elif GetEventFlag(9000):
                pass
        elif GetEventFlag(9000) or (IsPlayerDead() and not DoesSelfHaveSpEffect(9649)):
            pass
        """State 4"""
        assert t000003000_x36() and (not GetEventFlag(9000) and not IsPlayerDead())
    """Unused"""
    """State 5"""
    return 0

def t000003000_x25():
    """State 0,1"""
    assert t000003000_x26()
    """State 2"""
    return 0

def t000003000_x26():
    """State 0,1"""
    assert t000003000_x12(machine1=1104, val6=1104)
    """State 2"""
    return 0

def t000003000_x27():
    """State 0,1"""
    call = t000003000_x12(machine1=1201, val6=1201)
    if call.Get() == 1:
        """State 2"""
        assert t000003000_x6()
    elif call.Done():
        pass
    """State 3"""
    return 0

def t000003000_x28():
    """State 0,1"""
    call = t000003000_x12(machine1=1300, val6=1300)
    if call.Get() == 1:
        """State 2"""
        assert t000003000_x6()
    elif call.Done():
        pass
    """State 3"""
    return 0

def t000003000_x29():
    """State 0,1"""
    call = t000003000_x12(machine1=1301, val6=1301)
    if call.Get() == 1:
        """State 2"""
        assert t000003000_x6()
    elif call.Done():
        pass
    """State 3"""
    return 0

def t000003000_x30():
    """State 0,1"""
    call = t000003000_x12(machine1=1302, val6=1302)
    if call.Get() == 1:
        """State 2"""
        assert t000003000_x6()
    elif call.Done():
        pass
    """State 3"""
    return 0

def t000003000_x31(text2=_, flag1=_, mode6=1):
    """State 0,5"""
    assert t000003000_x2() and CheckSpecificPersonTalkHasEnded(0)
    """State 1"""
    TalkToPlayer(text2, -1, -1, 0)
    assert CheckSpecificPersonTalkHasEnded(0)
    """State 4"""
    if mode6 == 0:
        pass
    else:
        """State 3"""
        ReportConversationEndToHavokBehavior()
    """State 2"""
    SetEventFlag(flag1, FlagState.On)
    """State 6"""
    return 0

def t000003000_x32(text4=_, mode5=1):
    """State 0,4"""
    assert t000003000_x2() and CheckSpecificPersonTalkHasEnded(0)
    """State 1"""
    TalkToPlayer(text4, -1, -1, 0)
    assert CheckSpecificPersonTalkHasEnded(0)
    """State 3"""
    if mode5 == 0:
        pass
    else:
        """State 2"""
        ReportConversationEndToHavokBehavior()
    """State 5"""
    return 0

def t000003000_x33(text3=10002100, mode4=1):
    """State 0,4"""
    assert t000003000_x34() and CheckSpecificPersonTalkHasEnded(0)
    """State 1"""
    TalkToPlayer(text3, -1, -1, 1)
    """State 3"""
    if mode4 == 0:
        pass
    else:
        """State 2"""
        ReportConversationEndToHavokBehavior()
    """State 5"""
    return 0

def t000003000_x34():
    """State 0,1"""
    ClearTalkProgressData()
    StopEventAnimWithoutForcingConversationEnd(0)
    ReportConversationEndToHavokBehavior()
    """State 2"""
    return 0

def t000003000_x35():
    """State 0,1"""
    assert t000003000_x12(machine1=1002, val6=1002)
    """State 2"""
    return 0

def t000003000_x36():
    """State 0,1"""
    assert t000003000_x1()
    """State 2"""
    return 0

def t000003000_x37():
    """State 0,1"""
    if CheckSpecificPersonGenericDialogIsOpen(0):
        """State 2"""
        ForceCloseGenericDialog()
    else:
        pass
    """State 3"""
    if CheckSpecificPersonMenuIsOpen(-1, 0) and not CheckSpecificPersonGenericDialogIsOpen(0):
        """State 4"""
        ForceCloseMenu()
    else:
        pass
    """State 5"""
    return 0

def t000003000_x38():
    """State 0,1"""
    if not GetEventFlag(10000800):
        """State 2"""
        pass
    else:
        """State 3"""
        pass
    """State 4"""
    return 0

def t000003000_x39():
    """State 0,3"""
    assert t000003000_x32(text4=10002000, mode5=1)
    """State 1"""
    SetWorkValue(2, GetPlayerStat(PlayerStat.RuneLevel))
    """State 4"""
    def ExitPause():
        SetWorkValue(0, 0)
        SetWorkValue(1, 0)
    assert t000003000_x44()
    """State 2"""
    SetWorkValue(2, 0)
    """State 5"""
    return 0

def t000003000_x40():
    """State 0"""
    if GetEventFlag(110):
        """State 1"""
        pass
    elif not GetEventFlag(4681):
        """State 3"""
        assert t000003000_x73()
    elif not GetEventFlag(4680):
        """State 2"""
        pass
    elif GetEventFlag(108):
        """State 6"""
        assert t000003000_x75()
    elif GetEventFlag(11009260) and not GetEventFlag(400001):
        """State 4"""
        assert t000003000_x74()
    else:
        """State 5"""
        assert t000003000_x72()
    """State 7"""
    return 0

def t000003000_x41():
    """State 0,8"""
    assert GetCurrentStateElapsedTime() > 2
    """State 10"""
    assert t000003000_x31(text2=10001000, flag1=4681, mode6=1)
    """State 4"""
    ClearTalkListData()
    ClearPreviousMenuSelection()
    """State 5"""
    AddTalkListData(1, 21001000, -1)
    AddTalkListData(2, 21001001, -1)
    """State 6"""
    OpenConversationChoicesMenu(0)
    assert not (CheckSpecificPersonMenuIsOpen(12, 0) and not CheckSpecificPersonGenericDialogIsOpen(0))
    """State 1"""
    if GetTalkListEntryResult() == 1:
        """State 2,11"""
        assert t000003000_x81()
    else:
        """State 7,9"""
        assert t000003000_x31(text2=10001200, flag1=1042372700, mode6=1)
    """State 3"""
    SetEventFlag(4670, FlagState.Off)
    SetEventFlag(4698, FlagState.Off)
    """State 12"""
    return 0

def t000003000_x42():
    """State 0,1"""
    assert DoesSelfHaveSpEffect(9606)
    """State 2"""
    GiveSpEffectToPlayer(9602)
    def WhilePaused():
        GiveSpEffectToPlayer(9602)
    def ExitPause():
        GiveSpEffectToPlayer(9602)
    assert GetCurrentStateElapsedTime() > 9
    """State 3"""
    SetEventFlag(1054539205, FlagState.On)
    SetEventFlag(1054539200, FlagState.On)
    GiveSpEffectToPlayer(9601)
    def WhilePaused():
        GiveSpEffectToPlayer(9601)
    def ExitPause():
        GiveSpEffectToPlayer(9601)
    assert GetCurrentStateElapsedTime() > 2
    """State 5"""
    SetEventFlag(9000, FlagState.Off)
    SetEventFlag(9020, FlagState.Off)
    """State 4"""
    ChangeCamera(-1)
    Quit()
    """Unused"""
    """State 6"""
    return 0

def t000003000_x43():
    """State 0,1"""
    if GetEventFlag(10009656):
        """State 16"""
        assert t000003000_x61()
    elif GetEventFlag(1042379200):
        """State 4"""
        assert t000003000_x50()
    elif GetEventFlag(1042379202):
        """State 5"""
        assert t000003000_x51()
    elif GetEventFlag(1042372703):
        """State 26"""
        assert t000003000_x54()
    elif GetEventFlag(1042379206):
        """State 6"""
        assert t000003000_x52()
    elif GetEventFlag(1046389201):
        """State 7"""
        assert t000003000_x56(text2=10004100, flag1=1046389202, flag2=1046389203)
    elif GetEventFlag(1043349250):
        """State 8"""
        assert t000003000_x56(text2=10004400, flag1=1043349251, flag2=1043349252)
    elif GetEventFlag(1038509250):
        """State 9"""
        assert t000003000_x56(text2=10004500, flag1=1038509251, flag2=1038509252)
    elif GetEventFlag(1043539250):
        """State 10"""
        assert t000003000_x56(text2=10010100, flag1=1043539251, flag2=1043539252)
    elif GetEventFlag(11009255):
        """State 11"""
        assert t000003000_x56(text2=10010200, flag1=11009256, flag2=11009257)
    elif GetEventFlag(1043509200):
        """State 23"""
        assert t000003000_x56(text2=10010300, flag1=1043509201, flag2=1043509202)
    elif GetEventFlag(1054559200):
        """State 12"""
        assert t000003000_x56(text2=10010400, flag1=1054559201, flag2=1054559202)
    elif GetEventFlag(1036489250):
        """State 13"""
        assert t000003000_x57()
    elif GetEventFlag(1039519250):
        """State 14"""
        assert t000003000_x58()
    elif GetEventFlag(11009265):
        """State 27"""
        assert t000003000_x62()
    elif GetEventFlag(1037519200):
        """State 15"""
        assert t000003000_x59()
    elif GetEventFlag(1054539210):
        """State 19"""
        assert t000003000_x65()
    elif GetEventFlag(1054539215):
        """State 20"""
        assert t000003000_x66()
    elif GetEventFlag(35009350):
        """State 21"""
        assert t000003000_x67()
    elif GetEventFlag(35009352):
        """State 22"""
        assert t000003000_x68()
    elif GetEventFlag(35009355):
        """State 24"""
        assert t000003000_x69()
    elif GetEventFlag(35009358):
        """State 25"""
        assert t000003000_x70()
    elif GetEventFlag(11009270):
        """State 17"""
        assert t000003000_x63()
    elif GetEventFlag(11009275):
        """State 18"""
        assert t000003000_x64()
    elif GetEventFlag(4699):
        """State 3"""
        assert t000003000_x31(text2=999999997, flag1=11009251, mode6=1)
    else:
        """State 2"""
        pass
    """State 28"""
    return 0

def t000003000_x44():
    """State 0,1"""
    OpenSoul()
    """State 2"""
    assert t000003000_x33(text3=10002100, mode4=1) and not (CheckSpecificPersonMenuIsOpen(10, 0) and not CheckSpecificPersonGenericDialogIsOpen(0))
    """State 3"""
    return 0

def t000003000_x45():
    """State 0,7"""
    assert not GetEventFlag(9001)
    """State 10"""
    assert not DoesSelfHaveSpEffect(9606) or GetCurrentStateElapsedTime() > 10
    """State 5"""
    if GetEventFlag(4653):
        """State 1,12"""
        def WhilePaused():
            RequestAnimation(20004, -1)
        assert t000003000_x40()
    elif GetEventFlag(4654):
        """State 2,13"""
        assert t000003000_x38()
    elif GetEventFlag(4655):
        """State 3,15"""
        def WhilePaused():
            RequestAnimation(20004, -1)
        assert t000003000_x43()
    elif GetEventFlag(4657):
        """State 9,16"""
        def WhilePaused():
            RequestAnimation(20004, -1)
        assert t000003000_x53()
    elif GetEventFlag(4656):
        """State 4,11"""
        SetWorkValue(1, 0)
        def WhilePaused():
            GiveSpEffectToPlayer(9605)
            SetWorkValueIf(not GetWorkValue(1) > 1 and DoesPlayerHaveSpEffect(9604), 1, 1)
            RequestAnimationIf(GetWorkValue(1) > 1, 20002, -1)
            GiveSpEffectToPlayerIf(GetWorkValue(0) > 1, 9601)
            SetWorkValueIf(not GetWorkValue(0) > 1 and DoesSelfHaveSpEffect(9605), 0, 1)
            GiveSpEffectToSelfIf(GetWorkValue(1) > 1, 9602)
            SetWorkValueIf(GetWorkValue(0) > 1 and not DoesSelfHaveSpEffect(9605), 0, 0)
        def ExitPause():
            SetWorkValue(1, 0)
            SetWorkValue(0, 0)
        assert t000003000_x39()
    elif GetEventFlag(1054539200):
        """State 8,14"""
        t000003000_x42()
        def WhilePaused():
            RequestAnimation(20007, -1)
        Quit()
    else:
        """State 6"""
        pass
    """State 17"""
    return 0

def t000003000_x46():
    """State 0"""
    while True:
        """State 1"""
        assert GetEventFlag(4652)
        """State 2"""
        def ExitPause():
            SetEventFlag(4652, FlagState.Off)
            SetEventFlag(4653, FlagState.Off)
            SetEventFlag(4654, FlagState.Off)
            SetEventFlag(4655, FlagState.Off)
            SetEventFlag(4656, FlagState.Off)
            SetEventFlag(4657, FlagState.Off)
        assert t000003000_x45() or not GetEventFlag(4652)
        """State 3"""
        assert t000003000_x1()
    """Unused"""
    """State 4"""
    return 0

def t000003000_x47():
    """State 0"""
    Quit()
    """Unused"""
    """State 1"""
    return 0

def t000003000_x48():
    """State 0"""
    if GetEventFlag(10000851):
        """State 7,10"""
        assert t000003000_x32(text4=10010500, mode5=1)
    else:
        """State 8,11"""
        assert t000003000_x32(text4=10010700, mode5=1)
    """State 9"""
    SetEventFlag(10009655, FlagState.On)
    """State 3"""
    ClearTalkListData()
    ClearPreviousMenuSelection()
    """State 4"""
    AddTalkListData(1, 21001004, -1)
    """State 5"""
    OpenConversationChoicesMenu(0)
    assert not (CheckSpecificPersonMenuIsOpen(12, 0) and not CheckSpecificPersonGenericDialogIsOpen(0))
    """State 1"""
    if GetTalkListEntryResult() == 1:
        """State 2,12"""
        assert t000003000_x78()
    else:
        """State 6"""
        pass
    """State 13"""
    return 0

def t000003000_x49():
    """State 0,6"""
    assert t000003000_x31(text2=10014000, flag1=11009251, mode6=1)
    """State 1"""
    SetEventFlag(11002745, FlagState.On)
    """State 2"""
    SetEventFlag(11109687, FlagState.On)
    """State 5"""
    SetEventFlag(11009252, FlagState.On)
    """State 7"""
    call = t000003000_x3(lot1=100010)
    if call.Done() and not GetEventFlag(62528):
        """State 3,8"""
        assert t000003000_x4(action1=23241004)
    elif call.Done():
        """State 4"""
        pass
    """State 9"""
    return 0

def t000003000_x50():
    """State 0"""
    if not GetEventFlag(4681):
        """State 7,11"""
        assert t000003000_x31(text2=10001000, flag1=1042379201, mode6=1)
    else:
        """State 8,10"""
        assert t000003000_x31(text2=10001300, flag1=1042379201, mode6=1)
    """State 3"""
    ClearTalkListData()
    ClearPreviousMenuSelection()
    """State 4"""
    AddTalkListData(1, 21001000, -1)
    AddTalkListData(2, 21001001, -1)
    """State 5"""
    OpenConversationChoicesMenu(0)
    assert not (CheckSpecificPersonMenuIsOpen(12, 0) and not CheckSpecificPersonGenericDialogIsOpen(0))
    """State 1"""
    if GetTalkListEntryResult() == 1:
        """State 2,12"""
        assert t000003000_x81()
    else:
        """State 6,9"""
        assert t000003000_x31(text2=10001200, flag1=1042372700, mode6=1)
    """State 13"""
    return 0

def t000003000_x51():
    """State 0,2"""
    assert t000003000_x31(text2=10003000, flag1=1042379203, mode6=1)
    """State 1"""
    SetEventFlag(1042372703, FlagState.On)
    """State 3"""
    return 0

def t000003000_x52():
    """State 0,1"""
    assert t000003000_x31(text2=10003100, flag1=1042379207, mode6=1)
    """State 2"""
    return 0

def t000003000_x53():
    """State 0,1,2,3"""
    return 0

def t000003000_x54():
    """State 0,1"""
    assert t000003000_x31(text2=10003200, flag1=1042379209, mode6=1)
    """State 2"""
    return 0

def t000003000_x55():
    """State 0"""
    if not GetEventFlag(1046389200):
        """State 5,8"""
        assert t000003000_x32(text4=10004000, mode5=1)
    else:
        """State 6,7"""
        assert t000003000_x32(text4=10004300, mode5=1)
    """State 2"""
    ClearTalkListData()
    ClearPreviousMenuSelection()
    """State 3"""
    AddTalkListData(1, 21001002, -1)
    AddTalkListData(2, 21001003, -1)
    """State 4"""
    OpenConversationChoicesMenu(0)
    assert not (CheckSpecificPersonMenuIsOpen(12, 0) and not CheckSpecificPersonGenericDialogIsOpen(0))
    """State 1"""
    if GetTalkListEntryResult() == 1:
        """State 9"""
        return 0
    else:
        """State 10"""
        return 1

def t000003000_x56(text2=_, flag1=_, flag2=_):
    """State 0,3"""
    SetEventFlag(flag2, FlagState.On)
    if not GetEventFlag(1046382700):
        """State 4"""
        call = t000003000_x55()
        if call.Get() == 0:
            """State 5"""
            Label('L0')
            assert t000003000_x31(text2=text2, flag1=flag1, mode6=1)
            """State 2"""
            SetEventFlag(1046389200, FlagState.On)
            """State 7"""
            assert t000003000_x76()
        elif call.Done():
            """State 6"""
            assert t000003000_x31(text2=10004200, flag1=1046382700, mode6=1)
    else:
        """State 1"""
        Goto('L0')
    """State 8"""
    return 0

def t000003000_x57():
    """State 0,1"""
    assert t000003000_x31(text2=10011000, flag1=1036489251, mode6=1)
    """State 2"""
    return 0

def t000003000_x58():
    """State 0,1"""
    assert t000003000_x31(text2=10011100, flag1=1039519251, mode6=1)
    """State 2"""
    return 0

def t000003000_x59():
    """State 0,1"""
    assert t000003000_x31(text2=10013000, flag1=1037519201, mode6=1)
    """State 2"""
    return 0

def t000003000_x60():
    """State 0,1"""
    assert t000003000_x31(text2=10013100, flag1=11009260, mode6=1)
    """State 2"""
    return 0

def t000003000_x61():
    """State 0,1"""
    assert t000003000_x78()
    """State 2"""
    return 0

def t000003000_x62():
    """State 0,1"""
    assert t000003000_x31(text2=10014100, flag1=11009266, mode6=1)
    """State 2"""
    return 0

def t000003000_x63():
    """State 0,1"""
    assert t000003000_x31(text2=10015000, flag1=11009271, mode6=1)
    """State 2"""
    return 0

def t000003000_x64():
    """State 0,1"""
    assert t000003000_x31(text2=10016000, flag1=11009276, mode6=1)
    """State 2"""
    return 0

def t000003000_x65():
    """State 0,1"""
    assert t000003000_x31(text2=10017000, flag1=1054539211, mode6=1)
    """State 2"""
    return 0

def t000003000_x66():
    """State 0"""
    if not GetEventFlag(1054539216):
        """State 7"""
        assert t000003000_x31(text2=10017100, flag1=1054539216, mode6=1)
    else:
        """State 8"""
        assert t000003000_x31(text2=10017400, flag1=1054539216, mode6=1)
    """State 3"""
    ClearTalkListData()
    ClearPreviousMenuSelection()
    """State 4"""
    AddTalkListData(1, 21001005, -1)
    AddTalkListData(2, 21001006, -1)
    """State 5"""
    OpenConversationChoicesMenu(0)
    assert not (CheckSpecificPersonMenuIsOpen(12, 0) and not CheckSpecificPersonGenericDialogIsOpen(0))
    """State 1"""
    if GetTalkListEntryResult() == 1:
        """State 2,9"""
        assert t000003000_x32(text4=10017200, mode5=1)
        """State 11"""
        t000003000_x42()
        def WhilePaused():
            RequestAnimation(20007, -1)
        Quit()
    else:
        """State 6,10"""
        assert t000003000_x32(text4=10017300, mode5=1)
        """State 12"""
        return 0

def t000003000_x67():
    """State 0,2"""
    assert t000003000_x31(text2=10018000, flag1=35009351, mode6=1)
    """State 1"""
    SetEventFlag(35002732, FlagState.On)
    """State 3"""
    return 0

def t000003000_x68():
    """State 0,2"""
    assert t000003000_x31(text2=10018500, flag1=35009353, mode6=1)
    """State 1"""
    SetEventFlag(35002733, FlagState.On)
    """State 3"""
    return 0

def t000003000_x69():
    """State 0"""
    if GetEventFlag(35009356):
        """State 1,7"""
        assert t000003000_x32(text4=10018100, mode5=1)
    elif GetEventFlag(35009357):
        """State 2,8"""
        assert t000003000_x32(text4=10018200, mode5=1)
    elif GetEventFlag(1049539207):
        """State 3,5"""
        assert t000003000_x31(text2=10018100, flag1=35009356, mode6=1)
    else:
        """State 4,6"""
        assert t000003000_x31(text2=10018200, flag1=35009357, mode6=1)
    """State 9"""
    return 0

def t000003000_x70():
    """State 0,1"""
    assert t000003000_x31(text2=10018600, flag1=35009359, mode6=1)
    """State 2"""
    return 0

def t000003000_x71():
    """State 0"""
    if not GetEventFlag(400001):
        """State 2,4"""
        assert t000003000_x32(text4=10019000, mode5=1)
    else:
        """State 3,5"""
        assert t000003000_x32(text4=10019100, mode5=1)
    """State 1"""
    SetEventFlag(35009360, FlagState.On)
    """State 6"""
    return 0

def t000003000_x72():
    """State 0"""
    if (GetEventFlag(10000851) and not GetEventFlag(10009655) and not DoesPlayerHaveSpEffect(4270) and not DoesPlayerHaveSpEffect(4271)
        and not DoesPlayerHaveSpEffect(4272) and not DoesPlayerHaveSpEffect(4280) and not DoesPlayerHaveSpEffect(4282)
        and not DoesPlayerHaveSpEffect(4286)):
        """State 2"""
        def WhilePaused():
            RequestAnimation(20004, -1)
        assert t000003000_x48()
    elif ((GetEventFlag(3062) or GetEventFlag(3063) or GetEventFlag(3064) or GetEventFlag(3065)) and not GetEventFlag(10009655)
          and not DoesPlayerHaveSpEffect(4270) and not DoesPlayerHaveSpEffect(4271) and not DoesPlayerHaveSpEffect(4272)
          and not DoesPlayerHaveSpEffect(4280) and not DoesPlayerHaveSpEffect(4282) and not DoesPlayerHaveSpEffect(4286)):
        """State 4"""
        def WhilePaused():
            RequestAnimation(20004, -1)
        assert t000003000_x48()
    elif (not GetEventFlag(11009260) and not GetEventFlag(400001) and (GetEventFlag(11002741) or GetEventFlag(11002742)
          or GetEventFlag(11002743) or GetEventFlag(11002744))):
        """State 5"""
        def WhilePaused():
            RequestAnimation(20004, -1)
        assert t000003000_x60()
    elif GetEventFlag(9104) and not GetEventFlag(400001):
        """State 3"""
        def WhilePaused():
            RequestAnimation(20004, -1)
        assert t000003000_x49()
    else:
        """State 1"""
        pass
    """State 6"""
    return 0

def t000003000_x73():
    """State 0,1"""
    assert t000003000_x41()
    """State 2"""
    return 0

def t000003000_x74():
    """State 0"""
    if GetEventFlag(9104) and not GetEventFlag(400001):
        """State 2"""
        def WhilePaused():
            RequestAnimation(20004, -1)
        assert t000003000_x49()
    else:
        """State 1"""
        pass
    """State 3"""
    return 0

def t000003000_x75():
    """State 0,1"""
    assert t000003000_x71()
    """State 2"""
    return 0

def t000003000_x76():
    """State 0"""
    if GetEventFlag(1043509200):
        """State 1"""
        if not GetEventFlag(60846):
            """State 3"""
            AcquireGesture(104)
            SetEventFlag(60846, FlagState.On)
            assert GetCurrentStateElapsedTime() > 1 and not IsMenuOpen(MenuType.Bonfire)
        else:
            """State 4"""
            pass
    else:
        """State 2"""
        pass
    """State 5"""
    return 0

def t000003000_x77():
    """State 0,2"""
    assert t000003000_x79(text1=10010600, mode1=1) and (DoesPlayerHaveSpEffect(9601) or CheckSpecificPersonTalkHasEnded(0))
    """State 1"""
    RequestAnimationIf(GetWorkValue(1) > 1, 20002, -1)
    def WhilePaused():
        RequestAnimationIf(GetWorkValue(1) > 1, 20002, -1)
    def ExitPause():
        RequestAnimationIf(GetWorkValue(1) > 1, 20002, -1)
    assert t000003000_x80()
    """State 3"""
    return 0

def t000003000_x78():
    """State 0,1"""
    SetWorkValue(0, 0)
    SetWorkValue(1, 0)
    def WhilePaused():
        SetWorkValueIf(not GetWorkValue(1) > 1 and DoesPlayerHaveSpEffect(9604), 1, 1)
        SetWorkValueIf(not GetWorkValue(0) > 1 and DoesSelfHaveSpEffect(9605), 0, 1)
        GiveSpEffectToPlayer(9605)
        GiveSpEffectToPlayerIf(GetWorkValue(0) > 1, 9601)
        GiveSpEffectToSelfIf(GetWorkValue(1) > 1, 9602)
    def ExitPause():
        SetWorkValue(0, 0)
        SetWorkValue(1, 0)
    assert t000003000_x77()
    """State 2"""
    return 0

def t000003000_x79(text1=10010600, mode1=1):
    """State 0,4"""
    assert t000003000_x2() and CheckSpecificPersonTalkHasEnded(0)
    """State 1"""
    TalkToPlayer(text1, -1, -1, 0)
    """State 3"""
    if mode1 == 0:
        pass
    else:
        """State 2"""
        ReportConversationEndToHavokBehavior()
    """State 5"""
    return 0

def t000003000_x80():
    """State 0,3"""
    RequestAnimationIf(GetWorkValue(1) > 1, 20002, -1)
    def WhilePaused():
        RequestAnimationIf(GetWorkValue(1) > 1, 20002, -1)
    def ExitPause():
        RequestAnimationIf(GetWorkValue(1) > 1, 20002, -1)
    assert DoesPlayerHaveSpEffect(9601)
    """State 4"""
    assert GetCurrentStateElapsedTime() > 11 and CheckSpecificPersonTalkHasEnded(0)
    """State 2,1"""
    SetEventFlag(11109786, FlagState.On)
    SetEventFlag(104, FlagState.On)
    """State 5"""
    return 0

def t000003000_x81():
    """State 0"""
    if ComparePlayerInventoryNumber(ItemType.Goods, 130, CompareType.Equal, 0, False):
        """State 1,3"""
        assert t000003000_x31(text2=10001100, flag1=4680, mode6=1)
        """State 4"""
        assert t000003000_x3(lot1=100000)
        """State 5"""
        assert t000003000_x32(text4=10001105, mode5=1)
    else:
        """State 2,7"""
        assert t000003000_x31(text2=10001110, flag1=4680, mode6=1)
        """State 6"""
        assert t000003000_x3(lot1=100000)
    """State 8"""
    return 0

