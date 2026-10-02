package com.example.demo.membership;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/**
 * 旧库仅有 users 基础字段时，补齐会员相关列（首次启动执行 ALTER；列已存在则忽略异常）。
 */
@Component
@Order(1)
public class UsersMembershipColumnsMigration implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(UsersMembershipColumnsMigration.class);

    private final JdbcTemplate jdbcTemplate;

    public UsersMembershipColumnsMigration(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @Override
    public void run(ApplicationArguments args) {
        tryAlter(
                "ALTER TABLE users ADD COLUMN member_tier VARCHAR(20) NOT NULL DEFAULT 'free'"
        );
        tryAlter(
                "ALTER TABLE users ADD COLUMN member_until TIMESTAMP(6) NULL"
        );
    }

    private void tryAlter(String sql) {
        try {
            jdbcTemplate.execute(sql);
            log.info("[bitdance] applied migration: {}", sql);
        } catch (Exception e) {
            log.debug("[bitdance] skip migration (column may exist): {}", e.getMessage());
        }
    }
}
