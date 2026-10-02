package com.example.demo.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.math.BigDecimal;
import java.time.LocalDate;

public record BacktestResultDto(
        @JsonProperty("start_date")
        @JsonFormat(pattern = "yyyy-MM-dd")
        LocalDate startDate,

        @JsonProperty("end_date")
        @JsonFormat(pattern = "yyyy-MM-dd")
        LocalDate endDate,

        @JsonProperty("total_days")
        Long totalDays,

        @JsonProperty("profit_days")
        Long profitDays,

        @JsonProperty("loss_days")
        Long lossDays,

        @JsonProperty("capital")
        BigDecimal capital,

        @JsonProperty("end_balance")
        BigDecimal endBalance,

        @JsonProperty("max_drawdown")
        BigDecimal maxDrawdown,

        @JsonProperty("max_ddpercent")
        Double maxDdPercent,

        @JsonProperty("max_drawdown_duration")
        Long maxDrawdownDuration,

        @JsonProperty("total_net_pnl")
        BigDecimal totalNetPnl,

        @JsonProperty("daily_net_pnl")
        BigDecimal dailyNetPnl,

        @JsonProperty("total_commission")
        BigDecimal totalCommission,

        @JsonProperty("daily_commission")
        BigDecimal dailyCommission,

        @JsonProperty("total_slippage")
        BigDecimal totalSlippage,

        @JsonProperty("daily_slippage")
        BigDecimal dailySlippage,

        @JsonProperty("total_turnover")
        BigDecimal totalTurnover,

        @JsonProperty("daily_turnover")
        BigDecimal dailyTurnover,

        @JsonProperty("total_trade_count")
        Long totalTradeCount,

        @JsonProperty("daily_trade_count")
        Double dailyTradeCount,

        @JsonProperty("total_return")
        Double totalReturn,

        @JsonProperty("annual_return")
        Double annualReturn,

        @JsonProperty("daily_return")
        Double dailyReturn,

        @JsonProperty("return_std")
        Double returnStd,

        @JsonProperty("sharpe_ratio")
        Double sharpeRatio,

        @JsonProperty("ewm_sharpe")
        Double ewmSharpe,

        @JsonProperty("return_drawdown_ratio")
        Double returnDrawdownRatio,

        @JsonProperty("rgr_ratio")
        Double rgrRatio
) {}