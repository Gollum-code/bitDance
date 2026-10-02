package com.example.demo.controller;

import com.example.demo.auth.JwtPrincipal;
import com.example.demo.client.BacktestClient;
import com.example.demo.dto.BacktestRunRequest;
import com.example.demo.membership.MembershipService;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import reactor.core.publisher.Mono;

import java.util.Map;

@RestController
@RequestMapping("/api/backtest")
public class BacktestController {

    private final BacktestClient backtestClient;
    private final MembershipService membershipService;

    public BacktestController(BacktestClient backtestClient, MembershipService membershipService) {
        this.backtestClient = backtestClient;
        this.membershipService = membershipService;
    }

    @GetMapping("/run")
    public Map<String, Object> runDefault(
            @AuthenticationPrincipal JwtPrincipal principal,
            @RequestParam String strategyId
    ) {
        membershipService.assertCanUseStrategy(principal.userId(), strategyId);
        return backtestClient.getStrategy(strategyId).block();
    }

    @GetMapping("/run-symbol")
    public Map<String, Object> runWithSymbol(
            @AuthenticationPrincipal JwtPrincipal principal,
            @RequestParam String strategyId,
            @RequestParam(defaultValue = "600031.SSE") String vtSymbol
    ) {
        membershipService.assertCanUseStrategy(principal.userId(), strategyId);
        return backtestClient.getStrategy(strategyId, vtSymbol).block();
    }

    @GetMapping("/run-range")
    public Map<String, Object> runWithRange(
            @AuthenticationPrincipal JwtPrincipal principal,
            @RequestParam String strategyId,
            @RequestParam(defaultValue = "600031.SSE") String vtSymbol,
            @RequestParam(defaultValue = "2024-01-01") String start,
            @RequestParam(defaultValue = "2026-12-31") String end
    ) {
        membershipService.assertCanUseStrategy(principal.userId(), strategyId);
        return backtestClient.getStrategy(strategyId, vtSymbol, start, end).block();
    }

    @GetMapping("/run-custom")
    public Map<String, Object> runCustom(
            @AuthenticationPrincipal JwtPrincipal principal,
            @RequestParam String strategyId,
            @RequestParam(defaultValue = BacktestRunRequest.DEFAULT_VT_SYMBOL) String vtSymbol,
            @RequestParam(defaultValue = BacktestRunRequest.DEFAULT_START) String start,
            @RequestParam(defaultValue = BacktestRunRequest.DEFAULT_END) String end,
            @RequestParam(defaultValue = "0.0003") Double rate,
            @RequestParam(defaultValue = "0.01") Double slippage,
            @RequestParam(defaultValue = "1.0") Double size,
            @RequestParam(defaultValue = "0.01") Double pricetick,
            @RequestParam(defaultValue = "10000") Integer capital,
            @RequestParam(defaultValue = "3") Integer fastWindow,
            @RequestParam(defaultValue = "6") Integer slowWindow,
            @RequestParam(defaultValue = "4") Integer signalWindow,
            @RequestParam(defaultValue = "6") Integer atrWindow,
            @RequestParam(defaultValue = "1.2") Double atrMult,
            @RequestParam(defaultValue = "1000") Integer fixedSize
    ) {
        BacktestRunRequest request = new BacktestRunRequest(
                strategyId, vtSymbol, start, end,
                rate, slippage, size, pricetick,
                capital, fastWindow, slowWindow, signalWindow, atrWindow, atrMult, fixedSize
        ).normalize();
        validateRequest(request);
        membershipService.assertCanUseStrategy(principal.userId(), request.strategyId());
        return backtestClient.getStrategy(request).block();
    }

    @PostMapping("/run")
    public Map<String, Object> runByJson(
            @AuthenticationPrincipal JwtPrincipal principal,
            @RequestBody BacktestRunRequest payload
    ) {
        BacktestRunRequest request = payload.normalize();
        validateRequest(request);
        membershipService.assertCanUseStrategy(principal.userId(), request.strategyId());
        return backtestClient.getStrategy(request).block();
    }

    @GetMapping("/run-async")
    public Mono<Map<String, Object>> runAsync(
            @AuthenticationPrincipal JwtPrincipal principal,
            @RequestParam String strategyId
    ) {
        membershipService.assertCanUseStrategy(principal.userId(), strategyId);
        return backtestClient.getStrategy(strategyId);
    }

    @GetMapping("/strategies")
    public Map<String, Object> listStrategies(@AuthenticationPrincipal JwtPrincipal principal) {
        Map<String, Object> raw = backtestClient.listStrategies().block();
        if (raw == null) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "策略列表暂不可用");
        }
        return membershipService.annotateStrategies(raw, principal.userId());
    }

    private static void validateRequest(BacktestRunRequest request) {
        if (request.strategyId() == null || request.strategyId().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "strategyId 不能为空");
        }
        if (request.capital() <= 0 || request.size() <= 0 || request.pricetick() <= 0 || request.fixedSize() <= 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "capital/size/pricetick/fixedSize 必须大于 0");
        }
        if (request.fastWindow() <= 0 || request.slowWindow() <= 0 || request.signalWindow() <= 0 || request.atrWindow() <= 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "窗口参数必须为正整数");
        }
        if (request.slippage() < 0 || request.rate() < 0 || request.atrMult() < 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "rate/slippage/atrMult 不能小于 0");
        }
    }
}
