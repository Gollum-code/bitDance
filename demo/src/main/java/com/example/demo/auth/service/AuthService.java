package com.example.demo.auth.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.example.demo.auth.dto.AuthResponse;
import com.example.demo.auth.dto.LoginRequest;
import com.example.demo.auth.dto.RegisterRequest;
import com.example.demo.auth.dto.UserDto;
import com.example.demo.auth.entity.User;
import com.example.demo.auth.mapper.UserMapper;
import com.example.demo.membership.MembershipService;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Service
public class AuthService {
    private final UserMapper userMapper;
    private final JwtService jwtService;
    private final PasswordEncoder passwordEncoder;
    private final MembershipService membershipService;

    public AuthService(
            UserMapper userMapper,
            JwtService jwtService,
            PasswordEncoder passwordEncoder,
            MembershipService membershipService
    ) {
        this.userMapper = userMapper;
        this.jwtService = jwtService;
        this.passwordEncoder = passwordEncoder;
        this.membershipService = membershipService;
    }

    @Transactional
    public AuthResponse register(RegisterRequest request) {
        String username = request.username().trim();
        String email = request.email().trim().toLowerCase();

        if (existsUsernameIgnoreCase(username)) {
            throw new IllegalArgumentException("用户名已存在");
        }
        if (existsEmailIgnoreCase(email)) {
            throw new IllegalArgumentException("邮箱已被注册");
        }

        String hash = passwordEncoder.encode(request.password());
        User user = new User(username, email, hash, LocalDateTime.now());
        userMapper.insert(user);
        User saved = userMapper.selectById(user.getId());
        String token = jwtService.generateToken(saved.getId(), saved.getUsername());
        return new AuthResponse(token, toProfile(saved));
    }

    @Transactional(readOnly = true)
    public AuthResponse login(LoginRequest request) {
        String account = request.account().trim();
        String key = account.toLowerCase();
        User user = userMapper.selectOne(new LambdaQueryWrapper<User>()
                .apply("(LOWER(username) = {0} OR LOWER(email) = {1})", key, key));
        if (user == null) {
            throw new IllegalArgumentException("账号或密码错误");
        }

        if (!passwordEncoder.matches(request.password(), user.getPasswordHash())) {
            throw new IllegalArgumentException("账号或密码错误");
        }

        String token = jwtService.generateToken(user.getId(), user.getUsername());
        return new AuthResponse(token, toProfile(user));
    }

    @Transactional(readOnly = true)
    public UserDto me(Long userId) {
        User user = userMapper.selectById(userId);
        if (user == null) {
            throw new IllegalArgumentException("用户不存在或登录已失效");
        }
        return toUserDto(user);
    }

    private AuthResponse.UserProfile toProfile(User user) {
        boolean active = membershipService.isMember(user);
        String tier = user.getMemberTier() != null ? user.getMemberTier() : "free";
        return new AuthResponse.UserProfile(
                user.getId(),
                user.getUsername(),
                user.getEmail(),
                tier,
                user.getMemberUntil(),
                active
        );
    }

    private UserDto toUserDto(User user) {
        boolean active = membershipService.isMember(user);
        String tier = user.getMemberTier() != null ? user.getMemberTier() : "free";
        return new UserDto(
                user.getId(),
                user.getUsername(),
                user.getEmail(),
                tier,
                user.getMemberUntil(),
                active
        );
    }

    private boolean existsUsernameIgnoreCase(String username) {
        Long n = userMapper.selectCount(Wrappers.<User>lambdaQuery()
                .apply("LOWER(username) = {0}", username.toLowerCase()));
        return n != null && n > 0;
    }

    private boolean existsEmailIgnoreCase(String email) {
        Long n = userMapper.selectCount(Wrappers.<User>lambdaQuery()
                .apply("LOWER(email) = {0}", email.toLowerCase()));
        return n != null && n > 0;
    }
}
