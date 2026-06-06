-- 1. Short-Term Memory: Session Tracking
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_state VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Short-Term Memory: Message History
CREATE TABLE IF NOT EXISTS chat_messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL, -- Values: 'user', 'assistant', 'tool'
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Crucial for i3 speed: Index to instantly fetch history for context retention
CREATE INDEX IF NOT EXISTS idx_session_messages ON chat_messages(session_id, created_at);

-- 3. Long-Term Memory: Extracted User Insights
CREATE TABLE IF NOT EXISTS long_term_memory (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL, -- Values: 'preference', 'frequent_topic'
    content TEXT NOT NULL,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookup of specific preferences during routing
CREATE INDEX IF NOT EXISTS idx_memory_category ON long_term_memory(category);