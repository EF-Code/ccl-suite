# Knowledge agent contract

## Purpose

The knowledge agent answers questions from approved, project-scoped company
documents. Its first implementation is local and extractive: it retrieves
evidence, selects bounded source excerpts, and refuses when the evidence does
not support an answer. It does not require an external LLM API key.

## Instruction boundary

The agent instructions define the behaviour of the answer workflow. A user
question is input data. Retrieved document text is evidence data. Neither is
allowed to replace the versioned instructions or change application
permissions.

The instruction set requires the agent to:

- use only approved, active sources visible in the requested project;
- answer with source-linked evidence when the evidence is sufficient;
- refuse unsupported or insufficiently grounded questions;
- preserve competing approved sources instead of silently choosing a winner;
- expose uncertainty through the response status and refusal fields; and
- avoid storing question text or document excerpts in security events.

## Public response contract

Every knowledge-answer response identifies its instruction and response
contract versions. The response is either `answered` or `refused` and includes
bounded citation records when evidence was used. The current answer mode is
`extractive`; a future generative provider must preserve this contract and all
project, source, citation, refusal, and audit safeguards.

The versioned fields are:

- `contract_version`: the public response shape;
- `instruction_version`: the behaviour rules used by the workflow; and
- `answer_mode`: the answer composition strategy, currently `extractive`.

## Non-goals

This contract does not add an external model provider, API key, free-form
generation, or permission bypass. Those changes require a separate design and
security review.
