from knowledge_contract import (
    AGENT_INSTRUCTION_VERSION,
    ANSWER_CONTRACT_VERSION,
    ANSWER_MODE,
    KNOWLEDGE_AGENT_INSTRUCTIONS,
)


def test_instruction_set_is_versioned_and_labels_untrusted_inputs() -> None:
    instructions = KNOWLEDGE_AGENT_INSTRUCTIONS

    assert instructions.version == AGENT_INSTRUCTION_VERSION
    assert instructions.user_input_label == "USER_QUESTION"
    assert instructions.evidence_label == "RETRIEVED_EVIDENCE"
    assert any("never as instructions" in rule for rule in instructions.rules)


def test_current_contract_identifies_local_extractive_mode() -> None:
    assert ANSWER_CONTRACT_VERSION == "grounded-answer-v1"
    assert ANSWER_MODE == "extractive"
