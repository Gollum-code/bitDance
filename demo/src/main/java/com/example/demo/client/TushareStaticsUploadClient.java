package com.example.demo.client;

import org.springframework.core.io.ByteArrayResource;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.nio.file.Path;
import java.util.Map;

@Component
public class TushareStaticsUploadClient {

    private final WebClient webClient;

    public TushareStaticsUploadClient(WebClient.Builder builder) {
        this.webClient = builder.baseUrl("http://localhost:8000").build();
    }

    // ========== 重载 1：内存方式（Service 里用的）==========
    public Mono<Map> uploadCsv(String filename, byte[] fileBytes) {
        MultipartBodyBuilder builder = new MultipartBodyBuilder();
        builder.part("file", new ByteArrayResource(fileBytes) {
            @Override
            public String getFilename() {
                return filename;
            }
        });

        return webClient.post()
                .uri("/upload/csv")
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .bodyValue(builder.build())
                .retrieve()
                .onStatus(
                        status -> status.is4xxClientError() || status.is5xxServerError(),
                        resp -> resp.bodyToMono(String.class)
                                .flatMap(body -> Mono.error(new RuntimeException(
                                        "Python服务错误 [" + resp.statusCode() + "]: " + body)))
                )
                .bodyToMono(Map.class);
    }

    // ========== 重载 2：磁盘方式（可选）==========
    public Mono<Map> uploadCsv(Path filePath) {
        MultipartBodyBuilder builder = new MultipartBodyBuilder();
        builder.part("file", new FileSystemResource(filePath));

        return webClient.post()
                .uri("/upload/csv")
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .bodyValue(builder.build())
                .retrieve()
                .bodyToMono(Map.class);
    }
}