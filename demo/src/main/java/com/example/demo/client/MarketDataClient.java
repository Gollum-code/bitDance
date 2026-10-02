package com.example.demo.client;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.Map;
import java.util.Optional;

@Component
public class MarketDataClient {

    private static final ParameterizedTypeReference<Map<String, Object>> MAP_TYPE =
            new ParameterizedTypeReference<>() {};

    private final WebClient webClient;

    public MarketDataClient(
            WebClient.Builder webClientBuilder,
            @Value("${fastapi.base-url:http://localhost:8000}") String baseUrl
    ) {
        this.webClient = webClientBuilder.baseUrl(baseUrl).build();
    }

    public Mono<Map<String, Object>> listStocks(Optional<String> q, int limit) {
        return webClient.get()
                .uri(uriBuilder -> {
                    var b = uriBuilder.path("/api/market/stocks").queryParam("limit", limit);
                    q.filter(s -> !s.isBlank()).ifPresent(s -> b.queryParam("q", s));
                    return b.build();
                })
                .retrieve()
                .bodyToMono(MAP_TYPE)
                .timeout(Duration.ofSeconds(60));
    }

    public Mono<Map<String, Object>> getDaily(String tsCode, String startDate, String endDate) {
        return webClient.get()
                .uri(uriBuilder -> uriBuilder.path("/api/market/daily")
                        .queryParam("ts_code", tsCode)
                        .queryParam("start_date", startDate)
                        .queryParam("end_date", endDate)
                        .build())
                .retrieve()
                .bodyToMono(MAP_TYPE)
                .timeout(Duration.ofSeconds(120));
    }

    public Mono<Map<String, Object>> syncVnpy(Map<String, String> body) {
        return webClient.post()
                .uri("/api/market/sync-vnpy")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(body)
                .retrieve()
                .bodyToMono(MAP_TYPE)
                .timeout(Duration.ofSeconds(120));
    }
}
