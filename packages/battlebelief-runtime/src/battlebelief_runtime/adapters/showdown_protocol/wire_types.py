from __future__ import annotations

# Shared definition of every wire type that maps to a Core BattleEvent
# (state-bearing, VisibleEvidence, or IgnoredDisplayEvent), per the M1 plan's
# binding wire mapping. RoomPayloadClassifier and the ProtocolParser both use
# this single set, per the plan's "genau eine Definition" requirement.
BATTLE_EVENT_TYPES: frozenset[str] = frozenset(
    {
        # metadata
        "init",
        "player",
        "teamsize",
        "gametype",
        "gen",
        "tier",
        "rated",
        "rule",
        # preview
        "clearpoke",
        "poke",
        "teampreview",
        # progress
        "start",
        "turn",
        "win",
        "tie",
        # pokemon identity
        "move",
        "switch",
        "drag",
        "faint",
        "cant",
        "detailschange",
        "replace",
        # health
        "-damage",
        "-heal",
        "-sethp",
        # status
        "-status",
        "-curestatus",
        "-cureteam",
        # boosts
        "-boost",
        "-unboost",
        "-setboost",
        "-swapboost",
        "-copyboost",
        "-clearboost",
        "-clearallboost",
        "-clearpositiveboost",
        "-clearnegativeboost",
        "-invertboost",
        # field / side
        "-weather",
        "-fieldstart",
        "-fieldend",
        "-sidestart",
        "-sideend",
        "-swapsideconditions",
        # volatile / recharge
        "-start",
        "-end",
        "-singleturn",
        "-singlemove",
        "-mustrecharge",
        # item / ability
        "-item",
        "-enditem",
        "-ability",
        "-endability",
        # transform / form / tera
        "-transform",
        "-formechange",
        "-terastallize",
        # evidence
        "-crit",
        "-supereffective",
        "-resisted",
        "-immune",
        "-miss",
        "-fail",
        "-activate",
        "-block",
        "-notarget",
        "-nothing",
        "-hitcount",
        "-prepare",
        "-fieldactivate",
        # ignored display
        "upkeep",
        "t:",
        "-anim",
        "-hint",
        "-center",
        "-combine",
        "-waiting",
        "message",
        "-message",
    }
)

EVIDENCE_TYPES: frozenset[str] = frozenset(
    {
        "-crit",
        "-supereffective",
        "-resisted",
        "-immune",
        "-miss",
        "-fail",
        "-activate",
        "-block",
        "-notarget",
        "-nothing",
        "-hitcount",
        "-prepare",
        "-fieldactivate",
    }
)

IGNORED_DISPLAY_TYPES: frozenset[str] = frozenset(
    {
        "upkeep",
        "t:",
        "-anim",
        "-hint",
        "-center",
        "-combine",
        "-waiting",
        "message",
        "-message",
    }
)

ROOM_CONTROL_TYPES: frozenset[str] = frozenset(
    {
        "title",
        "users",
        "join",
        "j",
        "J",
        "leave",
        "l",
        "L",
        "name",
        "n",
        "N",
        "chat",
        "c",
        "c:",
        ":",
        "html",
        "uhtml",
        "uhtmlchange",
        "notify",
        "battle",
        "b",
        "B",
    }
)
