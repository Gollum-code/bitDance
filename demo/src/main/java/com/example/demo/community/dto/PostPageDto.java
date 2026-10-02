package com.example.demo.community.dto;

import java.util.List;

public record PostPageDto(
        List<PostSummaryDto> items,
        long total,
        int page,
        int size
) {
}
