package com.example.demo.community.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record CreatePostRequest(
        @NotBlank @Size(max = 200) String title,
        /**
         * 与 posts.content MEDIUMTEXT（约 16MB）对齐；双图 base64 在高分屏下易超过 2MB 字符，
         * 原先 2_000_000 会导致校验 400。
         */
        @NotBlank @Size(max = 15_000_000) String content
) {
}
