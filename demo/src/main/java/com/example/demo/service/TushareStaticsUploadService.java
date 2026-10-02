package com.example.demo.service;

import com.example.demo.client.TushareStaticsUploadClient;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import reactor.core.publisher.Mono;

import java.io.IOException;
import java.nio.file.Path;
import java.util.Map;

@Service
public class TushareStaticsUploadService {

    private final TushareStaticsUploadClient uploadClient;

    public TushareStaticsUploadService(TushareStaticsUploadClient uploadClient) {
        this.uploadClient = uploadClient;
    }

    /**
     * 上传 CSV 文件（内存方式）
     */
    public Map uploadCsv(MultipartFile file) throws IOException {
        return uploadClient.uploadCsv(
                file.getOriginalFilename(),
                file.getBytes()
        ).block();
    }

    /**
     * 上传 CSV 文件（指定文件名）
     */
    public Map uploadCsv(MultipartFile file, String filename) throws IOException {
        return uploadClient.uploadCsv(filename, file.getBytes()).block();
    }

    /**
     * 上传本地 CSV 文件（磁盘方式）
     */
    public Map uploadLocalCsv(Path filePath) {
        return uploadClient.uploadCsv(filePath).block();
    }

    /**
     * 异步上传（返回 Mono，调用方自己决定何时 block）
     */
    public Mono<Map> uploadCsvAsync(MultipartFile file) throws IOException {
        return uploadClient.uploadCsv(file.getOriginalFilename(), file.getBytes());
    }
}