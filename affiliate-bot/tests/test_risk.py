"""Run: python3 tests/test_risk.py  (no pytest needed)"""
import sys, tempfile, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bot.state import State
from bot.risk import classify, gate_reply, SAFE, HOLD, ESCALATE


def v(c, r=""):
    return classify(c, r).verdict


def test_safe_routine():
    for c, r in [
        ("Love this thread!", "Thanks so much for reading!"),
        ("Where can I get one?", "Link is in part 15 of the thread!"),
        ("How long does the battery last?", "About 15-20 blends per charge with USB-C."),
        ("Is it dishwasher safe?", "The cup is, hand wash the blade assembly."),
        ("What colors does it come in?", "Black, white, and navy blue."),
        ("Following for more", "Appreciate the follow!"),
    ]:
        assert v(c, r) == SAFE, c


def test_safe_borderline():
    # contains substrings of trigger words but not the words themselves
    assert v("Nice, the bottle looks sturdy. Is the botanical scent strong?") == SAFE   # 'bot' inside words
    assert v("Where did you get the scampi recipe?") == SAFE                           # 'scam' inside 'scampi'
    assert v("Thanks for the original idea!") == SAFE      # 'original' in comment alone is fine


def test_hold_cases():
    assert v("Sounds too good to be true...") == HOLD
    assert v("Sure, 'safety locks' 🙄") == HOLD
    assert v("How much did they pay you to say this?") == HOLD
    assert v("Bold claim about the ice crushing") == HOLD
    assert v("Is it safe for baby?") == HOLD
    assert v("Got lazada link too?") == HOLD               # competitor mention only


def test_hold_borderline_reply_claim():
    # innocent comment, but our drafted reply makes an unsourced claim
    assert v("Does it work well?", "Yes, it works well.") == SAFE
    assert v("Does it work well?", "100% guaranteed to work!") == HOLD
    assert v("Where to buy?", "This one is authentic, link below") == HOLD


def test_escalate_cases():
    for c in [
        "This is obviously a scam",
        "Fake story, you're clearly a bot",
        "Reported this post for misleading content",
        "You're scamming people with this affiliate garbage",
        "I'm filing a complaint with the authorities about this ad",
        "nak refund boleh? barang rosak",
        "Kena tipu beli kat sini",
        "Is it legit? Is this genuine or counterfeit?",
        "Lazada is cheaper, shopee scam",
        "I will find you and you will pay",
        "shut up idiot",
        "dasar penipu",
    ]:
        assert v(c) == ESCALATE, c


def test_escalate_borderline():
    assert v("Can I get my money back if it breaks?") == ESCALATE   # 'money back'
    assert v("Lazada cheaper la") == ESCALATE                       # competitor dispute
    assert v("not a scam right?") == ESCALATE                       # even a question about scam
    # escalate beats hold when both present
    assert v("too good to be true, scam?") == ESCALATE
    assert v("Is this ori ke?") == ESCALATE


def test_precedence_and_reasons():
    r = classify("sure, this is a scam")
    assert r.verdict == ESCALATE and any(x.startswith("scam_fraud") for x in r.reasons)
    assert r.action == "skip"
    assert classify("Love it").action == "send"
    assert classify("too good to be true").action == "queue"


def test_llm_can_only_raise():
    assert classify("hello", "", llm=lambda c, r: "ESCALATE").verdict == ESCALATE
    assert classify("hello", "", llm=lambda c, r: "HOLD").verdict == HOLD
    assert classify("hello", "", llm=lambda c, r: "SAFE").verdict == SAFE
    assert classify("this is a scam", "", llm=lambda c, r: "SAFE").verdict == ESCALATE
    def boom(c, r): raise RuntimeError("api down")
    assert classify("hello", "", llm=boom).verdict == HOLD          # fail closed
    assert classify("hello", "", llm=lambda c, r: "NOT SAFE").verdict in (HOLD, SAFE)


def test_gate_reply_persists_via_state():
    p = Path(tempfile.mkdtemp()) / "state.json"
    st = State(p)
    a = gate_reply("Love it", "Thanks!", state=st)
    assert a["action"] == "send" and "review_queue" not in st.data
    b = gate_reply("too good to be true", "It worked for me", state=st, comment_id="c1")
    assert b["action"] == "queue" and b["classification"] == HOLD
    c = gate_reply("this is a scam", "ignore", state=st, comment_id="c2")
    assert c["action"] == "skip" and c["classification"] == ESCALATE
    st2 = State(p)
    assert len(st2.data["review_queue"]) == 1 and st2.data["review_queue"][0]["drafted_reply"]
    assert len(st2.data["escalations"]) == 1 and "drafted_reply" not in st2.data["escalations"][0]


def run():
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print("PASS", name)
            except Exception:
                fails += 1; print("FAIL", name); traceback.print_exc()
    print(f"{'FAILED' if fails else 'ALL PASSED'} ({fails} failures)")
    return fails


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
