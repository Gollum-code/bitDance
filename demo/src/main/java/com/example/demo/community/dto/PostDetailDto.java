package com.example.demo.community.dto;

import java.time.LocalDateTime;

public record PostDetailDto(
        Long id,
        String title,
        String content,
        String authorUsername,
        int likeCount,
        int commentCount,
        LocalDateTime createdAt,
        boolean likedByMe
) {
}
