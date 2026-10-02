package com.example.demo.controller;

import com.example.demo.client.MarketDataClient;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

@RestController
@RequestMapping("/api/market")
public class MarketDataController {

    private final MarketDataClient marketDataClient;

    public MarketDataController(MarketDataClient marketDataClient) {
        this.marketDataClient = marketDataClient;
    }

    @GetMapping("/stocks")
    public Map<String, Object> stocks(
            @RequestParam(required = false) String q,
            @RequestParam(defaultValue = "80") int limit
    ) {
        Map<String, Object> raw = marketDataClient.listStocks(Optional.ofNullable(q), limit).block();
        if (raw == null) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "行情服务暂不可用");
        }
        return raw;
    }

    @GetMapping("/daily")
    public Map<String, Object> daily(
            @RequestParam String ts_code,
            @RequestParam String start_date,
            @RequestParam String end_date
    ) {
        Map<String, Object> raw = marketDataClient.getDaily(ts_code, start_date, end_date).block();
        if (raw == null) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "行情服务暂不可用");
        }
        return raw;
    }

    @PostMapping("/sync-vnpy")
    public Map<String, Object> syncVnpy(@RequestBody Map<String, String> body) {
        String ts = body.get("ts_code");
        if (ts == null || ts.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "ts_code 不能为空");
        }
        String start = Optional.ofNullable(body.get("start_date")).orElse("").trim();
        String end = Optional.ofNullable(body.get("end_date")).orElse("").trim();
        if (start.isEmpty() || end.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "start_date 与 end_date 不能为空");
        }
        Map<String, String> payload = new HashMap<>();
        payload.put("ts_code", ts.strip());
        payload.put("start_date", start);
        payload.put("end_date", end);
        Map<String, Object> raw = marketDataClient.syncVnpy(payload).block();
        if (raw == null) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "行情服务暂不可用");
        }
        return raw;
    }
}
