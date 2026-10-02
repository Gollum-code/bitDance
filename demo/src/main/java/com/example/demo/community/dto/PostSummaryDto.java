package com.example.demo.community.dto;

import java.time.LocalDateTime;

public record PostSummaryDto(
        Long id,
        String title,
        String excerpt,
        String authorUsername,
        int likeCount,
        int commentCount,
        LocalDateTime createdAt
) {
}
