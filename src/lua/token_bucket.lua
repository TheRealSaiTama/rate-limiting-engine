-- Atomic token bucket rate limiter (micro-token scaled for precision)
local key = KEYS[1]
local max_tokens_scaled = tonumber(ARGV[1])   -- e.g., 100000 for 100 tokens (x1000)
local refill_rate_scaled = tonumber(ARGV[2])  -- tokens per millisecond in micro-token units
local now_ms = tonumber(ARGV[3])

-- Fetch current state
local state = redis.call('HMGET', key, 'last_time_ms', 'tokens_scaled')
local last_time_ms = state[1] and tonumber(state[1]) or now_ms
local tokens_scaled = state[2] and tonumber(state[2]) or max_tokens_scaled

-- Refill based on elapsed time (ms)
local elapsed_ms = now_ms - last_time_ms
if elapsed_ms > 0 then
    local refill = math.floor(elapsed_ms * refill_rate_scaled)
    tokens_scaled = math.min(max_tokens_scaled, tokens_scaled + refill)
end

-- Consume 1000 micro-tokens = 1 real token
if tokens_scaled >= 1000 then
    tokens_scaled = tokens_scaled - 1000
    redis.call('HMSET', key, 'last_time_ms', now_ms, 'tokens_scaled', tokens_scaled)
    redis.call('EXPIRE', key, 120)  -- auto-cleanup
    return 1
else
    return 0
end
