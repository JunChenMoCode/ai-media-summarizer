/** 
 * Splits a partial suffix from the text.
 * Used to prevent emitting a partial tag (e.g., "<th") until it's complete or determined not to be a tag.
 */
const splitPartialSuffix = (text, tag) => {
    for (let i = 1; i < tag.length; i++) {
        if (text.endsWith(tag.slice(0, i))) {
            return { safe: text.slice(0, -i), rest: text.slice(-i) };
        }
    }
    return { safe: text, rest: '' };
};

/**
 * Processes a stream chunk to separate reasoning (<think>...</think>) from content.
 * Supports streaming of reasoning content while the tag is still open.
 * 
 * @param {string} chunk - The new incoming string chunk.
 * @param {object} state - The state object, must be preserved between calls. 
 *                         Initial structure: { buffer: '', inThink: false }
 * @returns {Array} - An array of objects { type: 'content' | 'reasoning', text: '...' }
 */
export const processStreamedOutput = (chunk, state) => {
    state.buffer += chunk;
    const out = [];

    while (true) {
        if (!state.inThink) {
            const startIdx = state.buffer.indexOf('<think>');
            if (startIdx === -1) {
                break;
            }
            if (startIdx > 0) {
                out.push({ type: 'content', text: state.buffer.slice(0, startIdx) });
            }
            state.buffer = state.buffer.slice(startIdx + 7);
            state.inThink = true;
        } else {
            const endIdx = state.buffer.indexOf('</think>');
            if (endIdx === -1) {
                break;
            }
            if (endIdx > 0) {
                out.push({ type: 'reasoning', text: state.buffer.slice(0, endIdx) });
            }
            state.buffer = state.buffer.slice(endIdx + 8);
            state.inThink = false;
        }
    }

    if (state.buffer.length > 0) {
        if (state.inThink) {
            const { safe, rest } = splitPartialSuffix(state.buffer, '</think>');
            if (safe) out.push({ type: 'reasoning', text: safe });
            state.buffer = rest;
        } else {
            const { safe, rest } = splitPartialSuffix(state.buffer, '<think>');
            if (safe) out.push({ type: 'content', text: safe });
            state.buffer = rest;
        }
    }

    return out;
};

/**
 * Flushes any remaining content in the buffer.
 * Should be called when the stream ends.
 * 
 * @param {object} state - The state object.
 * @returns {Array} - An array of objects { type: 'content' | 'reasoning', text: '...' }
 */
export const flushStreamBuffer = (state) => {
    if (!state.buffer) return [];
    const out = [];
    if (state.inThink) {
        // If stream ends while in think, output remaining buffer as reasoning
        out.push({ type: 'reasoning', text: state.buffer });
    } else {
        out.push({ type: 'content', text: state.buffer });
    }
    state.buffer = '';
    return out;
};
