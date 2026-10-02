package com.example.demo.membership;

import com.example.demo.auth.entity.User;
import com.example.demo.auth.mapper.UserMapper;
import com.example.demo.client.BacktestClient;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
@Service
public class MembershipService {

    private static final String TIER_MEMBER = "member";

    private final UserMapper userMapper;
    private final BacktestClient backtestClient;

    private volatile String cachedFreeStrategyId;
    private volatile long cachedFreeStrategyAt;

    public MembershipService(UserMapper userMapper, BacktestClient backtestClient) {
        this.userMapper = userMapper;
        this.backtestClient = backtestClient;
    }

    public boolean isMember(User user) {
        if (user == null) {
            return false;
        }
        if (!TIER_MEMBER.equalsIgnoreCase(safeTier(user.getMemberTier()))) {
            return false;
        }
        LocalDateTime until = user.getMemberUntil();
        return until == null || until.isAfter(LocalDateTime.now());
    }

    public boolean isMember(Long userId) {
        if (userId == null) {
            return false;
        }
        User u = userMapper.selectById(userId);
        return u != null && isMember(u);
    }

    public boolean mayUseAi(Long userId) {
        return isMember(userId);
    }

    /**
     * 非会员仅允许使用策略列表中的第一个策略（与 Python /strategy/list 返回顺序一致）。
     */
    public void assertCanUseStrategy(Long userId, String strategyId) {
        if (strategyId == null || strategyId.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "strategyId 不能为空");
        }
        if (isMember(userId)) {
            return;
        }
        String freeId = resolveFreeStrategyId();
        if (freeId == null || freeId.isBlank()) {
            freeId = "01";
        }
        String sid = strategyId.trim();
        if (freeId.equals(sid)) {
            return;
        }
        throw new ResponseStatusException(
                HttpStatus.FORBIDDEN,
                "非会员仅可使用列表中的首个策略，开通会员可解锁其余策略与 AI 问答"
        );
    }

    public void assertAiAccess(Long userId) {
        if (!mayUseAi(userId)) {
            throw new ResponseStatusException(
                    HttpStatus.FORBIDDEN,
                    "AI 问答为会员功能，请在会员中心开通会员"
            );
        }
    }

    public String resolveFreeStrategyId() {
        long now = System.currentTimeMillis();
        if (cachedFreeStrategyId != null && (now - cachedFreeStrategyAt) < 60_000L) {
            return cachedFreeStrategyId;
        }
        Map<String, Object> raw;
        try {
            raw = backtestClient.listStrategies().block();
        } catch (Exception e) {
            return cachedFreeStrategyId;
        }
        if (raw == null) {
            return cachedFreeStrategyId;
        }
        String id = extractFirstStrategyId(raw);
        if (id != null) {
            cachedFreeStrategyId = id;
            cachedFreeStrategyAt = now;
        }
        return id;
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> annotateStrategies(Map<String, Object> raw, Long userId) {
        if (raw == null) {
            return Map.of();
        }
        User user = userId != null ? userMapper.selectById(userId) : null;
        boolean member = isMember(user);
        Object listObj = raw.get("strategies");
        if (!(listObj instanceof List<?> list) || list.isEmpty()) {
            raw.put("memberActive", member);
            raw.put("freeStrategyId", resolveFreeStrategyId());
            return raw;
        }
        String freeId = extractFirstStrategyId(raw);
        if (freeId == null || freeId.isBlank()) {
            freeId = resolveFreeStrategyId();
        }
        if (freeId == null || freeId.isBlank()) {
            freeId = "01";
        }
        for (Object row : list) {
            if (row instanceof Map<?, ?> m) {
                Map<String, Object> mm = (Map<String, Object>) m;
                Object sidObj = mm.get("strategy_id");
                String sid = sidObj != null ? String.valueOf(sidObj).trim() : "";
                boolean locked = !member && !freeId.equals(sid);
                mm.put("locked", locked);
            }
        }
        raw.put("freeStrategyId", freeId);
        raw.put("memberActive", member);
        return raw;
    }

    private static String safeTier(String tier) {
        return tier == null ? "free" : tier;
    }

    @SuppressWarnings("unchecked")
    private static String extractFirstStrategyId(Map<String, Object> raw) {
        Object listObj = raw.get("strategies");
        if (!(listObj instanceof List<?> list) || list.isEmpty()) {
            return null;
        }
        return extractStrategyId(list.get(0));
    }

    private static String extractStrategyId(Object row) {
        if (!(row instanceof Map<?, ?> m)) {
            return null;
        }
        Object id = m.get("strategy_id");
        return id != null ? String.valueOf(id).trim() : null;
    }

    /** 演示：一键开通会员（无支付流程，生产环境应替换为支付回调开通）。 */
    @Transactional
    public void upgradeToMember(Long userId) {
        User u = userMapper.selectById(userId);
        if (u == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "用户不存在");
        }
        u.setMemberTier(TIER_MEMBER);
        u.setMemberUntil(null);
        userMapper.updateById(u);
    }
}
