-- Neon SQL Schema for Messages
-- Run this script in the Neon SQL Editor to create the required table.

CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(255) NOT NULL,
    user_message TEXT NOT NULL,
    bot_response TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Note: We index the phone_number and timestamp columns to make fetching conversation history fast.
CREATE INDEX idx_messages_phone_number ON messages(phone_number);
CREATE INDEX idx_messages_timestamp ON messages(timestamp DESC);
