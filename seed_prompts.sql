-- Prompt seed metadata for the execution-only AI Router.
-- Commercial authorization and customer-price fields
-- deliberately do not exist here. Task execution policy lives in
-- config/task_policies.json; provider/model metadata lives in
-- config/model_registry.json.

INSERT INTO ai_prompts (
    id, name, prompt_type, target_role, description,
    system_prompt, user_prompt_template, output_format,
    version, is_active, created_at, updated_at
) VALUES (
    uuid_generate_v4(),
    'execution_router_default_v1',
    'recommendation',
    'founder',
    'Fallback prompt metadata for execution-only routing.',
    'You are TechIT''s AI execution assistant. Follow the configured task policy and return accurate, safe, structured output.',
    'USER CONTEXT:\n{{ user_context }}\n\nTASK INPUT:\n{{ task_input }}',
    'Task-policy-defined output',
    1,
    TRUE,
    NOW(),
    NOW()
);
