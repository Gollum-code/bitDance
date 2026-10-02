package com.example.demo.client;

import com.example.demo.dto.ChatRequestDto;
import com.example.demo.dto.ChatResponseDto;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Duration;

@Component
public class ChatClient {

    private final WebClient webClient;

    // 支持从配置文件注入地址
    public ChatClient(
            WebClient.Builder webClientBuilder,
            @Value("${fastapi.base-url:http://localhost:8000}") String baseUrl
    ) {
        this.webClient = webClientBuilder
                .baseUrl(baseUrl)
                .build();
    }

    /**
     * 同步阻塞调用
     */
    public ChatResponseDto chat(ChatRequestDto request) {
        return chatAsync(request).block(Duration.ofSeconds(300));
    }

    /**
     * 异步非阻塞调用
     */
    public Mono<ChatResponseDto> chatAsync(ChatRequestDto request) {
        return webClient.post()
                .uri("/chat/completions")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(request)
                .retrieve()
                .onStatus(HttpStatusCode::isError, response ->
                        response.bodyToMono(String.class)
                                .flatMap(errorBody -> Mono.error(
                                        new ChatClientException(
                                                "FastAPI 错误: " + errorBody,
                                                response.statusCode().value()
                                        )
                                ))
                )
                .bodyToMono(ChatResponseDto.class);
    }

    /**
     * 开启新对话
     */
    public ChatResponseDto startConversation(String message) {
        return chat(new ChatRequestDto(message));
    }

    /**
     * 继续对话
     */
    public ChatResponseDto continueConversation(String conversationId, String message) {
        return chat(new ChatRequestDto(conversationId, message));
    }

    /**
     * 继续对话（带上下文长度控制）
     */
    public ChatResponseDto continueConversation(String conversationId, String message, int maxHistory) {
        return chat(new ChatRequestDto(conversationId, message, maxHistory));
    }

    /**
     * 同步清空会话
     */
    public void clearConversationSync(String conversationId) {
        clearConversationAsync(conversationId).block(Duration.ofSeconds(10));
    }

    /**
     * 异步清空会话（原方法改名）
     */
    public Mono<Void> clearConversationAsync(String conversationId) {
        return webClient.post()
                .uri(uriBuilder -> uriBuilder
                        .path("/chat/clear")
                        .queryParam("conversation_id", conversationId)
                        .build())
                .retrieve()
                .onStatus(HttpStatusCode::isError, response ->
                        response.bodyToMono(String.class)
                                .flatMap(errorBody -> Mono.error(
                                        new ChatClientException(
                                                "清空会话失败: " + errorBody,
                                                response.statusCode().value()
                                        )
                                ))
                )
                .bodyToMono(Void.class);
    }

    // ============ 内部异常类 ============
    public static class ChatClientException extends RuntimeException {
        private final int statusCode;

        public ChatClientException(String message, int statusCode) {
            super(message);
            this.statusCode = statusCode;
        }

        public int getStatusCode() {
            return statusCode;
        }
    }
}