package com.example.demo.auth.dto;

import java.time.LocalDateTime;

public record AuthResponse(
        String token,
        UserProfile user
) {
    public record UserProfile(
            Long id,
            String username,
            String email,
            String memberTier,
            LocalDateTime memberUntil,
            boolean memberActive
    ) {
    }
}

