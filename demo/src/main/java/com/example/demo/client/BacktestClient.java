package com.example.demo.client;

import com.example.demo.dto.BacktestRunRequest;
import org.springframework.stereotype.Service;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.Map;

@Service
public class BacktestClient {
    private static final ParameterizedTypeReference<Map<String, Object>> MAP_TYPE =
            new ParameterizedTypeReference<>() {};

    private final WebClient webClient;

    public BacktestClient(WebClient.Builder builder) {
        // 你的 Python 服务地址
        this.webClient = builder.baseUrl("http://localhost:8000").build();
    }

    public Mono<Map<String, Object>> listStrategies() {
        return webClient.get()
                .uri("/strategy/list")
                .retrieve()
                .bodyToMono(MAP_TYPE)
                .timeout(Duration.ofSeconds(30));
    }


    // ========== 重载 1：只传 strategyId ==========
    public Mono<Map<String, Object>> getStrategy(String strategyId) {
        // 调用下一个重载（2个参数）
        return getStrategy(strategyId, BacktestRunRequest.DEFAULT_VT_SYMBOL);
    }

    // ========== 重载 2：指定品种 ==========
    public Mono<Map<String, Object>> getStrategy(String strategyId, String vtSymbol) {
        // 调用下一个重载（4个参数）
        return getStrategy(strategyId, vtSymbol, BacktestRunRequest.DEFAULT_START, BacktestRunRequest.DEFAULT_END);
    }

    // ========== 重载 3：指定品种 + 时间区间（最常用）==========
    public Mono<Map<String, Object>> getStrategy(
            String strategyId,
            String vtSymbol,
            String start,
            String end
    ) {
        // 调用全参数方法
        return getStrategy(
                strategyId,
                vtSymbol,
                start,
                end,
                BacktestRunRequest.DEFAULT_RATE,
                BacktestRunRequest.DEFAULT_SLIPPAGE,
                BacktestRunRequest.DEFAULT_SIZE,
                BacktestRunRequest.DEFAULT_PRICETICK,
                BacktestRunRequest.DEFAULT_CAPITAL,
                BacktestRunRequest.DEFAULT_FAST_WINDOW,
                BacktestRunRequest.DEFAULT_SLOW_WINDOW,
                BacktestRunRequest.DEFAULT_SIGNAL_WINDOW,
                BacktestRunRequest.DEFAULT_ATR_WINDOW,
                BacktestRunRequest.DEFAULT_ATR_MULT,
                BacktestRunRequest.DEFAULT_FIXED_SIZE
        );
    }

    public Mono<Map<String, Object>> getStrategy(BacktestRunRequest request) {
        return getStrategy(
                request.strategyId(),
                request.vtSymbol(),
                request.start(),
                request.end(),
                request.rate(),
                request.slippage(),
                request.size(),
                request.pricetick(),
                request.capital(),
                request.fastWindow(),
                request.slowWindow(),
                request.signalWindow(),
                request.atrWindow(),
                request.atrMult(),
                request.fixedSize()
        );
    }

    // ========== 全参数方法（终极版）==========
    public Mono<Map<String, Object>> getStrategy(
            String strategyId,
            String vtSymbol,
            String start,
            String end,
            Double rate,
            Double slippage,
            Double size,
            Double pricetick,
            Integer capital,
            Integer fastWindow,
            Integer slowWindow,
            Integer signalWindow,
            Integer atrWindow,
            Double atrMult,
            Integer fixedSize
    ) {
        return webClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/strategy/{strategyId}")
                        .queryParam("vt_symbol", vtSymbol)
                        .queryParam("start", start)
                        .queryParam("end", end)
                        .queryParam("rate", rate)
                        .queryParam("slippage", slippage)
                        .queryParam("size", size)
                        .queryParam("pricetick", pricetick)
                        .queryParam("capital", capital)
                        .queryParam("fast_window", fastWindow)
                        .queryParam("slow_window", slowWindow)
                        .queryParam("signal_window", signalWindow)
                        .queryParam("atr_window", atrWindow)
                        .queryParam("atr_mult", atrMult)
                        .queryParam("fixed_size", fixedSize)
                        .build(strategyId))
                .retrieve()
                .bodyToMono(MAP_TYPE)
                .timeout(Duration.ofSeconds(60));
    }
}


