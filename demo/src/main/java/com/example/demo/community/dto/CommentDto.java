package com.example.demo.community.dto;

import java.time.LocalDateTime;

public record CommentDto(
        Long id,
        String body,
        String authorUsername,
        int likeCount,
        LocalDateTime createdAt,
        boolean likedByMe
) {
}
