package com.example.demo.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonInclude(JsonInclude.Include.NON_NULL)
public record ChatRequestDto(
        @JsonProperty("conversation_id")
        String conversationId,

        @JsonProperty("message")
        String message,

        @JsonProperty("model")
        String model,

        @JsonProperty("max_history")
        Integer maxHistory,      // 新增：控制上下文长度，默认20

        @JsonProperty("max_tokens")
        Integer maxTokens
) {
    // 便捷构造：开启新对话
    public ChatRequestDto(String message) {
        this(null, message, null, null, null);
    }

    // 便捷构造：继续对话
    public ChatRequestDto(String conversationId, String message) {
        this(conversationId, message, null, null, null);
    }

    // 完整构造：带上下文控制
    public ChatRequestDto(String conversationId, String message, Integer maxHistory) {
        this(conversationId, message, null, maxHistory, null);
    }
}