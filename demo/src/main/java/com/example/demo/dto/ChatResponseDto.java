package com.example.demo.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Map;

public record ChatResponseDto(
        @JsonProperty("conversation_id")
        String conversationId,

        @JsonProperty("reply")
        String reply,

        @JsonProperty("model")
        String model,

        @JsonProperty("usage")
        Map<String, Object> usage
) {}