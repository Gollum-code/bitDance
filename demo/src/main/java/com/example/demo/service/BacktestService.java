package com.example.demo.service;



import com.example.demo.client.BacktestClient;
import org.springframework.stereotype.Service;
import java.util.Map;

@Service
public class BacktestService {

    private final BacktestClient backtestClient;

    public BacktestService(BacktestClient backtestClient) {
        this.backtestClient = backtestClient;
    }

    // 业务层：可以在这里加缓存、日志、异常转换
    public Map<String, Object> runBacktest(String strategyId) {
        return backtestClient.getStrategy(strategyId).block();
    }
}