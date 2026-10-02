package com.example.demo.community.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.demo.auth.entity.User;
import com.example.demo.auth.mapper.UserMapper;
import com.example.demo.community.dto.CommentDto;
import com.example.demo.community.dto.CreateCommentRequest;
import com.example.demo.community.dto.CreatePostRequest;
import com.example.demo.community.dto.LikeResponse;
import com.example.demo.community.dto.PostDetailDto;
import com.example.demo.community.dto.PostPageDto;
import com.example.demo.community.dto.PostSummaryDto;
import com.example.demo.community.entity.Comment;
import com.example.demo.community.entity.CommentLike;
import com.example.demo.community.entity.Post;
import com.example.demo.community.entity.PostLike;
import com.example.demo.community.mapper.CommentLikeMapper;
import com.example.demo.community.mapper.CommentMapper;
import com.example.demo.community.mapper.PostLikeMapper;
import com.example.demo.community.mapper.PostMapper;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

@Service
public class CommunityService {

    private static final int EXCERPT_MAX = 180;

    private final PostMapper postMapper;
    private final CommentMapper commentMapper;
    private final PostLikeMapper postLikeMapper;
    private final CommentLikeMapper commentLikeMapper;
    private final UserMapper userMapper;

    public CommunityService(
            PostMapper postMapper,
            CommentMapper commentMapper,
            PostLikeMapper postLikeMapper,
            CommentLikeMapper commentLikeMapper,
            UserMapper userMapper
    ) {
        this.postMapper = postMapper;
        this.commentMapper = commentMapper;
        this.postLikeMapper = postLikeMapper;
        this.commentLikeMapper = commentLikeMapper;
        this.userMapper = userMapper;
    }

    @Transactional
    public PostDetailDto createPost(Long authorId, CreatePostRequest req) {
        LocalDateTime now = LocalDateTime.now();
        Post p = new Post();
        p.setAuthorId(authorId);
        p.setTitle(req.title().trim());
        p.setContent(req.content().trim());
        p.setLikeCount(0);
        p.setCommentCount(0);
        p.setCreatedAt(now);
        p.setUpdatedAt(now);
        postMapper.insert(p);
        User author = userMapper.selectById(authorId);
        String authorName = author != null ? author.getUsername() : "?";
        return new PostDetailDto(
                p.getId(),
                p.getTitle(),
                p.getContent(),
                authorName,
                0,
                0,
                p.getCreatedAt(),
                false
        );
    }

    public PostPageDto listPosts(String q, int page, int size) {
        int p = Math.max(page, 1);
        int s = Math.min(Math.max(size, 1), 50);
        LambdaQueryWrapper<Post> w = new LambdaQueryWrapper<>();
        if (StringUtils.hasText(q)) {
            String pattern = "%" + q.trim() + "%";
            w.and(x -> x.like(Post::getTitle, pattern).or().like(Post::getContent, pattern));
        }
        Long totalObj = postMapper.selectCount(w);
        long total = totalObj != null ? totalObj : 0;
        w.orderByDesc(Post::getCreatedAt);
        int offset = (p - 1) * s;
        w.last("LIMIT " + s + " OFFSET " + offset);
        List<Post> records = postMapper.selectList(w);
        List<PostSummaryDto> items = toSummaries(records);
        return new PostPageDto(items, total, p, s);
    }

    public PostDetailDto getPost(Long id, Long viewerUserId) {
        Post post = postMapper.selectById(id);
        if (post == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "帖子不存在");
        }
        User author = userMapper.selectById(post.getAuthorId());
        String authorName = author != null ? author.getUsername() : "?";
        boolean liked = viewerUserId != null && postLikeExists(post.getId(), viewerUserId);
        int lc = post.getLikeCount() != null ? post.getLikeCount() : 0;
        int cc = post.getCommentCount() != null ? post.getCommentCount() : 0;
        return new PostDetailDto(
                post.getId(),
                post.getTitle(),
                post.getContent(),
                authorName,
                lc,
                cc,
                post.getCreatedAt(),
                liked
        );
    }

    @Transactional
    public LikeResponse togglePostLike(Long postId, Long userId) {
        Post post = postMapper.selectById(postId);
        if (post == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "帖子不存在");
        }
        LambdaQueryWrapper<PostLike> lw = new LambdaQueryWrapper<PostLike>()
                .eq(PostLike::getPostId, postId)
                .eq(PostLike::getUserId, userId);
        PostLike existing = postLikeMapper.selectOne(lw);
        int base = post.getLikeCount() != null ? post.getLikeCount() : 0;
        if (existing != null) {
            postLikeMapper.deleteById(existing.getId());
            post.setLikeCount(Math.max(0, base - 1));
            postMapper.updateById(post);
            return new LikeResponse(false, post.getLikeCount());
        }
        PostLike pl = new PostLike();
        pl.setPostId(postId);
        pl.setUserId(userId);
        pl.setCreatedAt(LocalDateTime.now());
        postLikeMapper.insert(pl);
        post.setLikeCount(base + 1);
        postMapper.updateById(post);
        return new LikeResponse(true, post.getLikeCount());
    }

    public List<PostSummaryDto> trending(int limit) {
        int lim = Math.min(Math.max(limit, 1), 30);
        LambdaQueryWrapper<Post> w = new LambdaQueryWrapper<Post>()
                .orderByDesc(Post::getLikeCount)
                .orderByDesc(Post::getCreatedAt)
                .last("LIMIT " + lim);
        List<Post> posts = postMapper.selectList(w);
        return toSummaries(posts);
    }

    public List<CommentDto> listComments(Long postId, String sort, Long viewerUserId) {
        Post post = postMapper.selectById(postId);
        if (post == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "帖子不存在");
        }
        LambdaQueryWrapper<Comment> cw = new LambdaQueryWrapper<Comment>().eq(Comment::getPostId, postId);
        String s = sort != null ? sort.trim().toLowerCase() : "new";
        if ("likes".equals(s)) {
            cw.orderByDesc(Comment::getLikeCount).orderByDesc(Comment::getCreatedAt);
        } else {
            cw.orderByDesc(Comment::getCreatedAt);
        }
        List<Comment> comments = commentMapper.selectList(cw);
        if (comments.isEmpty()) {
            return List.of();
        }
        Set<Long> authorIds = comments.stream().map(Comment::getAuthorId).collect(Collectors.toSet());
        Map<Long, String> names = usernames(authorIds);
        List<Long> cids = comments.stream().map(Comment::getId).toList();
        Set<Long> liked = likedCommentIds(viewerUserId, cids);
        return comments.stream().map(c -> new CommentDto(
                c.getId(),
                c.getBody(),
                names.getOrDefault(c.getAuthorId(), "?"),
                c.getLikeCount() != null ? c.getLikeCount() : 0,
                c.getCreatedAt(),
                liked.contains(c.getId())
        )).toList();
    }

    @Transactional
    public CommentDto createComment(Long postId, Long authorId, CreateCommentRequest req) {
        Post post = postMapper.selectById(postId);
        if (post == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "帖子不存在");
        }
        Comment c = new Comment();
        c.setPostId(postId);
        c.setAuthorId(authorId);
        c.setBody(req.body().trim());
        c.setLikeCount(0);
        c.setCreatedAt(LocalDateTime.now());
        commentMapper.insert(c);
        int cc = post.getCommentCount() != null ? post.getCommentCount() : 0;
        post.setCommentCount(cc + 1);
        postMapper.updateById(post);
        User author = userMapper.selectById(authorId);
        String authorName = author != null ? author.getUsername() : "?";
        return new CommentDto(
                c.getId(),
                c.getBody(),
                authorName,
                0,
                c.getCreatedAt(),
                false
        );
    }

    @Transactional
    public LikeResponse toggleCommentLike(Long commentId, Long userId) {
        Comment comment = commentMapper.selectById(commentId);
        if (comment == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "评论不存在");
        }
        LambdaQueryWrapper<CommentLike> lw = new LambdaQueryWrapper<CommentLike>()
                .eq(CommentLike::getCommentId, commentId)
                .eq(CommentLike::getUserId, userId);
        CommentLike existing = commentLikeMapper.selectOne(lw);
        int base = comment.getLikeCount() != null ? comment.getLikeCount() : 0;
        if (existing != null) {
            commentLikeMapper.deleteById(existing.getId());
            comment.setLikeCount(Math.max(0, base - 1));
            commentMapper.updateById(comment);
            return new LikeResponse(false, comment.getLikeCount());
        }
        CommentLike cl = new CommentLike();
        cl.setCommentId(commentId);
        cl.setUserId(userId);
        cl.setCreatedAt(LocalDateTime.now());
        commentLikeMapper.insert(cl);
        comment.setLikeCount(base + 1);
        commentMapper.updateById(comment);
        return new LikeResponse(true, comment.getLikeCount());
    }

    private boolean postLikeExists(Long postId, Long userId) {
        Long n = postLikeMapper.selectCount(new LambdaQueryWrapper<PostLike>()
                .eq(PostLike::getPostId, postId)
                .eq(PostLike::getUserId, userId));
        return n != null && n > 0;
    }

    private Set<Long> likedCommentIds(Long userId, List<Long> commentIds) {
        if (userId == null || commentIds.isEmpty()) {
            return Collections.emptySet();
        }
        List<CommentLike> likes = commentLikeMapper.selectList(new LambdaQueryWrapper<CommentLike>()
                .eq(CommentLike::getUserId, userId)
                .in(CommentLike::getCommentId, commentIds));
        return likes.stream().map(CommentLike::getCommentId).collect(Collectors.toSet());
    }

    private Map<Long, String> usernames(Collection<Long> ids) {
        if (ids == null || ids.isEmpty()) {
            return Map.of();
        }
        List<User> users = userMapper.selectList(new LambdaQueryWrapper<User>().in(User::getId, ids));
        return users.stream().collect(Collectors.toMap(User::getId, User::getUsername));
    }

    private List<PostSummaryDto> toSummaries(List<Post> posts) {
        if (posts == null || posts.isEmpty()) {
            return List.of();
        }
        Set<Long> authorIds = posts.stream().map(Post::getAuthorId).filter(Objects::nonNull).collect(Collectors.toSet());
        Map<Long, String> names = usernames(authorIds);
        return posts.stream().map(p -> new PostSummaryDto(
                p.getId(),
                p.getTitle(),
                excerpt(p.getContent()),
                names.getOrDefault(p.getAuthorId(), "?"),
                p.getLikeCount() != null ? p.getLikeCount() : 0,
                p.getCommentCount() != null ? p.getCommentCount() : 0,
                p.getCreatedAt()
        )).toList();
    }

    private static String excerpt(String content) {
        if (content == null || content.isEmpty()) {
            return "";
        }
        String s = content;
        // 列表摘要：去掉 Markdown 内嵌图片（尤其 data URL）以免占满摘要长度
        s = s.replaceAll("!\\[[^\\]]*\\]\\(data:[^\\)]+\\)", "[图片]");
        s = s.replaceAll("\\s+", " ").trim();
        if (s.length() <= EXCERPT_MAX) {
            return s;
        }
        return s.substring(0, EXCERPT_MAX) + "…";
    }
}
