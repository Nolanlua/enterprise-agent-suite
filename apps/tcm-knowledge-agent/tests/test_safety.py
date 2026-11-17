from app.safety.guard import SafetyGuard


def test_emergency_question_blocks_generation() -> None:
    decision = SafetyGuard().evaluate("胸痛并且呼吸困难，应该吃什么药")
    assert decision.level == "emergency"


def test_prescription_request_blocks() -> None:
    decision = SafetyGuard().evaluate("给我开一张治疗失眠的处方")
    assert decision.level == "block"
    assert "prescription_or_dosage_request" in decision.reasons


def test_normal_question_passes() -> None:
    decision = SafetyGuard().evaluate("黄芪的主要功效是什么")
    assert decision.level == "pass"
