
-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- pgvector indexes for semantic search
CREATE INDEX IF NOT EXISTS idx_user_skill_vec
    ON user_skill_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_idea_vec
    ON idea_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Marketplace ranking function (GSIS + WCRS)
CREATE OR REPLACE FUNCTION top_startups(
    p_limit       int     DEFAULT 20,
    p_industry    text    DEFAULT NULL,
    p_stage       text    DEFAULT NULL,
    p_min_gsis    float   DEFAULT 0
)
RETURNS TABLE (
    project_id         uuid,
    title              text,
    industry           text,
    stage              text,
    gsis_score         float,
    wcrs_score         float,
    decay_factor       float,
    unicorn_score      float,
    investment_score   float,
    evi_i_score        float
) LANGUAGE sql STABLE AS $$
    SELECT p.id, p.title, p.industry, p.stage::text,
           p.gsis_score, p.wcrs_score, p.decay_factor,
           p.unicorn_potential_score, p.investment_score, p.evi_i_score
    FROM projects p
    WHERE p.gsis_score >= p_min_gsis
      AND (p_industry IS NULL OR p.industry = p_industry)
      AND (p_stage    IS NULL OR p.stage::text = p_stage)
    ORDER BY p.gsis_score DESC, p.wcrs_score DESC
    LIMIT p_limit;
$$;

-- IP leak detection (pgvector cosine similarity)
CREATE OR REPLACE FUNCTION find_similar_ideas(
    query_embedding vector(1536),
    threshold       float DEFAULT 0.90,
    max_results     int   DEFAULT 10
)
RETURNS TABLE (project_id uuid, title text, similarity float)
LANGUAGE sql STABLE AS $$
    SELECT ie.project_id, p.title,
           1 - (ie.embedding <=> query_embedding) AS similarity
    FROM idea_embeddings ie
    JOIN projects p ON p.id = ie.project_id
    WHERE ie.leak_detection_enabled = true
      AND 1 - (ie.embedding <=> query_embedding) >= threshold
    ORDER BY ie.embedding <=> query_embedding
    LIMIT max_results;
$$;

-- Skill matching (vector similarity for matching engine)
CREATE OR REPLACE FUNCTION find_skill_matches(
    query_embedding vector(1536),
    threshold       float DEFAULT 0.70,
    max_results     int   DEFAULT 20
)
RETURNS TABLE (user_id uuid, similarity float)
LANGUAGE sql STABLE AS $$
    SELECT ue.user_id,
           1 - (ue.embedding <=> query_embedding) AS similarity
    FROM user_skill_embeddings ue
    WHERE 1 - (ue.embedding <=> query_embedding) >= threshold
    ORDER BY ue.embedding <=> query_embedding
    LIMIT max_results;
$$;

-- Live score view (decay recomputed on read)
CREATE OR REPLACE VIEW project_scores_live AS
SELECT
    p.id, p.title, p.stage, p.industry,
    p.gsis_score, p.wcrs_score, p.unicorn_potential_score,
    p.investment_score, p.evi_i_score,
    p.days_since_update,
    EXP(-0.02 * p.days_since_update) AS live_decay_factor,
    p.wcrs_score * EXP(-0.02 * p.days_since_update) AS live_adjusted_score,
    p.gsis_score * EXP(-0.02 * p.days_since_update) AS live_gsis_adjusted
FROM projects p;

-- Monthly credit burn view
CREATE OR REPLACE VIEW monthly_credit_burn AS
SELECT
    u.id AS user_id, u.subscription_tier,
    u.subscription_credits_remaining,
    u.payg_credits_balance,
    COUNT(cl.id) AS transactions_this_month,
    SUM(ABS(cl.credits_delta)) FILTER (WHERE cl.event_type = 'credits_deducted')
        AS credits_consumed,
    SUM(cl.usd_charged_payg) AS payg_usd_spent
FROM users u
LEFT JOIN credit_ledger cl
    ON cl.user_id = u.id
    AND cl.created_at >= date_trunc('month', NOW())
GROUP BY u.id, u.subscription_tier,
         u.subscription_credits_remaining, u.payg_credits_balance;

-- Stagnation view
CREATE OR REPLACE VIEW stagnating_projects AS
SELECT p.id, p.title, p.owner_id, p.days_since_update,
       p.decay_factor,
       ROUND(((1 - p.decay_factor) * 100)::numeric, 1) AS score_penalty_pct,
       p.gsis_score, p.wcrs_score
FROM projects p
WHERE p.decay_factor < 0.70
  AND p.stage NOT IN ('scale')
ORDER BY p.decay_factor ASC;
