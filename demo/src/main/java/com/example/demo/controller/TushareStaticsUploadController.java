package com.example.demo.controller;

import com.example.demo.service.TushareStaticsUploadService;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import reactor.core.publisher.Mono;

import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;

@RestController
@RequestMapping("/api/tusharestaticsupload")
public class TushareStaticsUploadController {

    private final TushareStaticsUploadService uploadService;

    public TushareStaticsUploadController(TushareStaticsUploadService uploadService) {
        this.uploadService = uploadService;
    }

//用这个应该可以吧
    /**
     * 上传 CSV 文件（内存方式，最常用）
     * POST /api/tushare/upload/csv
     */
    @PostMapping(value = "/upload/csv", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Map uploadCsv(@RequestParam("file") MultipartFile file) throws IOException {
        return uploadService.uploadCsv(file);
    }



    //下面的可作为替补方法，不优先考虑使用
    /**
     * 上传 CSV 文件（指定文件名）
     * POST /api/tushare/upload/csv/rename?filename=custom.csv
     */
    @PostMapping(value = "/upload/csv/rename", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Map uploadCsvWithName(
            @RequestParam("file") MultipartFile file,
            @RequestParam("filename") String filename
    ) throws IOException {
        return uploadService.uploadCsv(file, filename);
    }

    /**
     * 上传本地 CSV 文件（磁盘方式，服务端指定路径）
     * POST /api/tushare/upload/local?filePath=/path/to/file.csv
     */
    @PostMapping("/upload/local")
    public Map uploadLocalCsv(@RequestParam("filePath") String filePath) {
        Path path = Paths.get(filePath);
        return uploadService.uploadLocalCsv(path);
    }

    /**
     * 异步上传 CSV 文件
     * POST /api/tushare/upload/csv/async
     */
    @PostMapping(value = "/upload/csv/async", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Mono<Map> uploadCsvAsync(@RequestParam("file") MultipartFile file) throws IOException {
        return uploadService.uploadCsvAsync(file);
    }
}
