package com.example.demo.auth.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;

import java.time.LocalDateTime;

@TableName("users")
public class User {
    @TableId(type = IdType.AUTO)
    private Long id;

    private String username;

    private String email;

    @TableField("password_hash")
    private String passwordHash;

    @TableField("created_at")
    private LocalDateTime createdAt;

    /**
     * free | member
     */
    @TableField("member_tier")
    private String memberTier;

    /** 会员到期时间；null 表示不限期（演示开通常用） */
    @TableField("member_until")
    private LocalDateTime memberUntil;

    public User() {
    }

    public User(String username, String email, String passwordHash, LocalDateTime createdAt) {
        this.username = username;
        this.email = email;
        this.passwordHash = passwordHash;
        this.createdAt = createdAt;
        this.memberTier = "free";
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public String getPasswordHash() {
        return passwordHash;
    }

    public void setPasswordHash(String passwordHash) {
        this.passwordHash = passwordHash;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }

    public String getMemberTier() {
        return memberTier;
    }

    public void setMemberTier(String memberTier) {
        this.memberTier = memberTier;
    }

    public LocalDateTime getMemberUntil() {
        return memberUntil;
    }

    public void setMemberUntil(LocalDateTime memberUntil) {
        this.memberUntil = memberUntil;
    }
}
