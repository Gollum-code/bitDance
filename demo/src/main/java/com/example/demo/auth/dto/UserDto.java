package com.example.demo.auth.dto;

import java.time.LocalDateTime;

public record UserDto(
        Long id,
        String username,
        String email,
        String memberTier,
        LocalDateTime memberUntil,
        boolean memberActive
) {
}

