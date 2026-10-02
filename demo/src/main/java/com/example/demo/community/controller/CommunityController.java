package com.example.demo.community.controller;

import com.example.demo.auth.JwtPrincipal;
import com.example.demo.community.dto.CommentDto;
import com.example.demo.community.dto.CreateCommentRequest;
import com.example.demo.community.dto.CreatePostRequest;
import com.example.demo.community.dto.LikeResponse;
import com.example.demo.community.dto.PostDetailDto;
import com.example.demo.community.dto.PostPageDto;
import com.example.demo.community.dto.PostSummaryDto;
import com.example.demo.community.service.CommunityService;
import jakarta.validation.Valid;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/community")
public class CommunityController {

    private final CommunityService communityService;

    public CommunityController(CommunityService communityService) {
        this.communityService = communityService;
    }

    @GetMapping("/trending")
    public List<PostSummaryDto> trending(@RequestParam(defaultValue = "10") int limit) {
        return communityService.trending(limit);
    }

    @GetMapping("/posts")
    public PostPageDto listPosts(
            @RequestParam(required = false) String q,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size
    ) {
        return communityService.listPosts(q, page, size);
    }

    @PostMapping("/posts")
    public PostDetailDto createPost(
            @AuthenticationPrincipal JwtPrincipal principal,
            @Valid @RequestBody CreatePostRequest req
    ) {
        return communityService.createPost(principal.userId(), req);
    }

    @GetMapping("/posts/{id}")
    public PostDetailDto getPost(
            @PathVariable Long id,
            @AuthenticationPrincipal JwtPrincipal principal
    ) {
        Long viewerId = principal != null ? principal.userId() : null;
        return communityService.getPost(id, viewerId);
    }

    @PostMapping("/posts/{id}/like")
    public LikeResponse togglePostLike(
            @PathVariable Long id,
            @AuthenticationPrincipal JwtPrincipal principal
    ) {
        return communityService.togglePostLike(id, principal.userId());
    }

    @GetMapping("/posts/{id}/comments")
    public List<CommentDto> listComments(
            @PathVariable Long id,
            @RequestParam(defaultValue = "new") String sort,
            @AuthenticationPrincipal JwtPrincipal principal
    ) {
        Long viewerId = principal != null ? principal.userId() : null;
        return communityService.listComments(id, sort, viewerId);
    }

    @PostMapping("/posts/{id}/comments")
    public CommentDto createComment(
            @PathVariable Long id,
            @AuthenticationPrincipal JwtPrincipal principal,
            @Valid @RequestBody CreateCommentRequest req
    ) {
        return communityService.createComment(id, principal.userId(), req);
    }

    @PostMapping("/comments/{id}/like")
    public LikeResponse toggleCommentLike(
            @PathVariable Long id,
            @AuthenticationPrincipal JwtPrincipal principal
    ) {
        return communityService.toggleCommentLike(id, principal.userId());
    }
}
