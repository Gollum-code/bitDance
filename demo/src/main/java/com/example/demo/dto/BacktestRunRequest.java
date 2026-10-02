package com.example.demo.dto;

public record BacktestRunRequest(
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
    public static final String DEFAULT_VT_SYMBOL = "600031.SSE";
    public static final String DEFAULT_START = "2024-01-01";
    public static final String DEFAULT_END = "2026-12-31";
    public static final Double DEFAULT_RATE = 0.0003;
    public static final Double DEFAULT_SLIPPAGE = 0.01;
    public static final Double DEFAULT_SIZE = 1.0;
    public static final Double DEFAULT_PRICETICK = 0.01;
    public static final Integer DEFAULT_CAPITAL = 10_000;
    public static final Integer DEFAULT_FAST_WINDOW = 3;
    public static final Integer DEFAULT_SLOW_WINDOW = 6;
    public static final Integer DEFAULT_SIGNAL_WINDOW = 4;
    public static final Integer DEFAULT_ATR_WINDOW = 6;
    public static final Double DEFAULT_ATR_MULT = 1.2;
    public static final Integer DEFAULT_FIXED_SIZE = 1000;

    public BacktestRunRequest normalize() {
        return new BacktestRunRequest(
                strategyId == null ? null : strategyId.trim(),
                isBlank(vtSymbol) ? DEFAULT_VT_SYMBOL : vtSymbol.trim(),
                isBlank(start) ? DEFAULT_START : start.trim(),
                isBlank(end) ? DEFAULT_END : end.trim(),
                rate == null ? DEFAULT_RATE : rate,
                slippage == null ? DEFAULT_SLIPPAGE : slippage,
                size == null ? DEFAULT_SIZE : size,
                pricetick == null ? DEFAULT_PRICETICK : pricetick,
                capital == null ? DEFAULT_CAPITAL : capital,
                fastWindow == null ? DEFAULT_FAST_WINDOW : fastWindow,
                slowWindow == null ? DEFAULT_SLOW_WINDOW : slowWindow,
                signalWindow == null ? DEFAULT_SIGNAL_WINDOW : signalWindow,
                atrWindow == null ? DEFAULT_ATR_WINDOW : atrWindow,
                atrMult == null ? DEFAULT_ATR_MULT : atrMult,
                fixedSize == null ? DEFAULT_FIXED_SIZE : fixedSize
        );
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}
