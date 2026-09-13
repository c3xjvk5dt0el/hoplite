#ifndef MOMENTUM_CORE_TEST
#property copyright "Momentum Candle XAU"
#property version   "1.03"
#property strict
#property description "XAUUSD M5/M15 market entry after momentum close, default RR 1:1 and 0.01 lots."

#include <Trade\Trade.mqh>
#endif

bool MomentumSignal(const double open, const double high, const double low,
                    const double close, const double min_body,
                    const double max_wick_pct, const bool conservative,
                    bool &buy)
{
   if(!MathIsValidNumber(open) || !MathIsValidNumber(high) || !MathIsValidNumber(low) ||
      !MathIsValidNumber(close) || !MathIsValidNumber(min_body) || !MathIsValidNumber(max_wick_pct))
      return false;
   const double range = high - low;
   const double body = MathAbs(close - open);
   if(range <= 0.0 || min_body <= 0.0 || max_wick_pct < 0.0 ||
      max_wick_pct > 100.0 || high < MathMax(open, close) ||
      low > MathMin(open, close) || body < min_body || body == 0.0)
      return false;

   const double upper = high - MathMax(open, close);
   const double lower = MathMin(open, close) - low;
   if((upper + lower) / range > max_wick_pct / 100.0)
      return false;

   buy = close > open;
   // Preserve the original Pine script's conservative wick direction.
   return !conservative || (buy ? lower < upper : upper < lower);
}

double PriceUp(const double price, const double tick)
{
   return MathCeil(price / tick - 1e-9) * tick;
}

double PriceDown(const double price, const double tick)
{
   return MathFloor(price / tick + 1e-9) * tick;
}

bool TargetFromEntry(const bool buy, const double entry, const double sl,
                     const double tick, const double reward_risk, double &tp)
{
   if(!MathIsValidNumber(entry) || !MathIsValidNumber(sl) || !MathIsValidNumber(tick) ||
      !MathIsValidNumber(reward_risk) || entry <= 0 || sl <= 0 || tick <= 0 || reward_risk <= 0)
      return false;
   const double risk = buy ? entry - sl : sl - entry;
   if(risk <= 0)
      return false;
   tp = buy ? PriceUp(entry + reward_risk * risk, tick)
            : PriceDown(entry - reward_risk * risk, tick);
   return MathIsValidNumber(tp) && tp > 0 && (buy ? tp > entry : tp < entry);
}

bool MarketLevels(const bool buy, const double high, const double low,
                  const double atr, const double bid, const double ask, const double tick,
                  const double stop_atr, const double reward_risk,
                  double &entry, double &sl, double &tp)
{
   if(!MathIsValidNumber(high) || !MathIsValidNumber(low) || !MathIsValidNumber(atr) ||
      !MathIsValidNumber(bid) || !MathIsValidNumber(ask) || !MathIsValidNumber(tick) ||
      !MathIsValidNumber(stop_atr) || high <= low || low <= 0 || atr <= 0 ||
      bid <= 0 || ask < bid || tick <= 0 || stop_atr < 0)
      return false;
   const double spread = ask - bid;
   const double stop_buffer = MathMax(atr * stop_atr, tick);
   // Candle OHLC uses Bid; market buys and short exits use Ask.
   entry = buy ? ask : bid;
   sl = buy ? PriceDown(low - stop_buffer, tick) : PriceUp(high + stop_buffer + spread, tick);
   return TargetFromEntry(buy, entry, sl, tick, reward_risk, tp);
}

bool MarketStopsValid(const bool buy, const double bid, const double ask,
                      const double sl, const double tp, const double distance)
{
   if(!MathIsValidNumber(bid) || !MathIsValidNumber(ask) || !MathIsValidNumber(sl) ||
      !MathIsValidNumber(tp) || !MathIsValidNumber(distance) || bid <= 0 || ask < bid ||
      sl <= 0 || tp <= 0 || distance <= 0)
      return false;
   return buy ? bid - sl >= distance && tp - bid >= distance
              : sl - ask >= distance && ask - tp >= distance;
}

double FixedVolume(const double requested, const double min_lot,
                   const double max_lot, const double step)
{
   if(!MathIsValidNumber(requested) ||
      !MathIsValidNumber(min_lot) || !MathIsValidNumber(max_lot) || !MathIsValidNumber(step))
      return 0.0;
   if(requested <= 0.0 || min_lot <= 0.0 || max_lot < min_lot || step <= 0.0 ||
      requested < min_lot || requested > max_lot)
      return 0.0;

   const double volume = NormalizeDouble(requested, 8);
   const double grid_volume = MathFloor(volume / step + 0.5) * step;
   // Reject incompatible lots instead of silently rounding up or down.
   if(volume <= 0.0 || MathAbs(volume - requested) > 1e-10 ||
      MathAbs(grid_volume - volume) > 1e-10)
      return 0.0;
   return volume;
}

// Local C++ tests compile only the math above; MT5 compiles the complete EA.
#ifndef MOMENTUM_CORE_TEST

input group "Momentum - original Pine thresholds"
input double InpM5BodyPips = 35.0;
input double InpM15BodyPips = 45.0;
input double InpGoldPipSize = 0.10;
input double InpMaxWickPct = 30.0;
input bool   InpConservativeWick = false;
input bool   InpUseConsolidation = false;
input int    InpConsolidationBars = 3;

input group "Trend and volatility"
input bool            InpUseEMA = true;
input ENUM_TIMEFRAMES InpEMATimeframe = PERIOD_H1;
input int             InpEMAPeriod = 50;
input int             InpATRPeriod = 14;
input double          InpMaxCandleATR = 2.5;

input group "Entry / stop / target"
input double InpSLBufferATR = 0.15;
input double InpRewardRisk = 1.0;
input int    InpMaxSignalDelaySeconds = 30;

input group "Fixed lot and execution"
input double InpFixedLots = 0.01;
input double InpMaxSpreadPrice = 0.50;
input ulong  InpDeviationPoints = 50;
input ulong  InpMagic = 26091301;

CTrade trade;
int atr_handle = INVALID_HANDLE;
int ema_handle = INVALID_HANDLE;
datetime last_processed_bar = 0;
datetime last_target_sync = 0;
bool target_warning = false;
const string MARKET_COMMENT = "MomentumXAU_Market";

void ReleaseIndicators()
{
   if(atr_handle != INVALID_HANDLE)
      IndicatorRelease(atr_handle);
   if(ema_handle != INVALID_HANDLE)
      IndicatorRelease(ema_handle);
   atr_handle = INVALID_HANDLE;
   ema_handle = INVALID_HANDLE;
}

int OnInit()
{
   string name = _Symbol;
   StringToUpper(name);
   const bool gold_usd =
      (SymbolInfoString(_Symbol, SYMBOL_CURRENCY_BASE) == "XAU" &&
       SymbolInfoString(_Symbol, SYMBOL_CURRENCY_PROFIT) == "USD") ||
      StringFind(name, "XAUUSD") == 0;
   if(!gold_usd || (_Period != PERIOD_M5 && _Period != PERIOD_M15))
   {
      Print("Use an XAUUSD M5 or M15 chart (broker suffixes supported).");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(InpM5BodyPips <= 0 || InpM15BodyPips <= 0 || InpGoldPipSize <= 0 ||
      InpMaxWickPct <= 0 || InpMaxWickPct >= 100 ||
      InpConsolidationBars < 1 || InpConsolidationBars > 10 ||
      InpEMAPeriod < 1 || InpATRPeriod < 1 || InpMaxCandleATR <= 0 ||
      !MathIsValidNumber(InpSLBufferATR) || InpSLBufferATR < 0 ||
      !MathIsValidNumber(InpRewardRisk) || InpRewardRisk < 1 ||
      InpMaxSignalDelaySeconds < 1 ||
      InpMaxSignalDelaySeconds >= PeriodSeconds(_Period) ||
      !MathIsValidNumber(InpFixedLots) || InpFixedLots <= 0 ||
      InpMaxSpreadPrice <= 0 || InpMagic == 0 ||
      (InpUseEMA && PeriodSeconds(InpEMATimeframe) < PeriodSeconds(_Period)))
   {
      Print("Invalid inputs. Fixed lots must be positive; EMA TF must be >= chart TF.");
      return INIT_PARAMETERS_INCORRECT;
   }

   if(FixedVolume(InpFixedLots, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN),
                  SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX),
                  SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP)) <= 0.0)
   {
      PrintFormat("Fixed lots %.8f incompatible with broker min/max/step. Lot will not be changed.", InpFixedLots);
      return INIT_PARAMETERS_INCORRECT;
   }

   const long modes = SymbolInfoInteger(_Symbol, SYMBOL_ORDER_MODE);
   if((modes & SYMBOL_ORDER_MARKET) == 0 || (modes & SYMBOL_ORDER_SL) == 0 ||
      (modes & SYMBOL_ORDER_TP) == 0 ||
      SymbolInfoInteger(_Symbol, SYMBOL_CHART_MODE) != SYMBOL_CHART_MODE_BID ||
      SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE) <= 0)
   {
      Print("Broker must support Bid candles, market orders and attached SL/TP.");
      return INIT_FAILED;
   }

   if(!trade.SetTypeFillingBySymbol(_Symbol))
   {
      Print("Cannot determine a supported market filling policy.");
      return INIT_FAILED;
   }

   atr_handle = iATR(_Symbol, _Period, InpATRPeriod);
   if(InpUseEMA)
      ema_handle = iMA(_Symbol, InpEMATimeframe, InpEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(atr_handle == INVALID_HANDLE || (InpUseEMA && ema_handle == INVALID_HANDLE))
   {
      ReleaseIndicators();
      return INIT_FAILED;
   }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetAsyncMode(false);
   trade.SetDeviationInPoints(InpDeviationPoints);
   trade.SetMarginMode();
   last_processed_bar = iTime(_Symbol, _Period, 0);
   PrintFormat("Ready. MARKET after candle close; RR=1:%.2f; fixed lots=%.8f. Waiting for next closed candle.",
               InpRewardRisk, InpFixedLots);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   ReleaseIndicators();
}

bool HasSymbolExposure()
{
   // Block manual and other-EA exposure too, including on netting accounts.
   for(int i = PositionsTotal() - 1; i >= 0; --i)
      if(PositionGetTicket(i) != 0 && PositionGetString(POSITION_SYMBOL) == _Symbol)
         return true;
   for(int i = OrdersTotal() - 1; i >= 0; --i)
      if(OrderGetTicket(i) != 0 && OrderGetString(ORDER_SYMBOL) == _Symbol)
         return true;
   return false;
}

bool ReadIndicator(const int handle, const int warmup, double &value)
{
   double buffer[1];
   if(BarsCalculated(handle) < warmup + 2 || CopyBuffer(handle, 0, 1, 1, buffer) != 1)
      return false;
   value = buffer[0];
   return MathIsValidNumber(value) && value != EMPTY_VALUE && value > 0.0;
}

bool TradingAllowed(const bool buy)
{
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED) ||
      !AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) || !AccountInfoInteger(ACCOUNT_TRADE_EXPERT))
      return false;
   const long mode = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE);
   return mode == SYMBOL_TRADE_MODE_FULL ||
          (buy && mode == SYMBOL_TRADE_MODE_LONGONLY) ||
          (!buy && mode == SYMBOL_TRADE_MODE_SHORTONLY);
}

void WarnTargetOnce(const string message)
{
   if(!target_warning)
      Print("TP alignment pending: ", message, ". Current broker SL/TP unchanged; check Journal.");
   target_warning = true;
}

void AlignTakeProfit()
{
   const datetime now = TimeCurrent();
   if(now == last_target_sync)
      return;
   last_target_sync = now;
   bool found = false;
   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      const ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol ||
         (ulong)PositionGetInteger(POSITION_MAGIC) != InpMagic ||
         PositionGetString(POSITION_COMMENT) != MARKET_COMMENT)
         continue;
      found = true;
      const bool buy = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
      const double entry = PositionGetDouble(POSITION_PRICE_OPEN);
      const double sl = PositionGetDouble(POSITION_SL);
      const double current_tp = PositionGetDouble(POSITION_TP);
      const double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      double tp = 0;
      if(!TargetFromEntry(buy, entry, sl, tick_size, InpRewardRisk, tp))
      {
         WarnTargetOnce("invalid fill price, SL or tick size");
         continue;
      }
      tp = NormalizeDouble(tp, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS));
      if(MathAbs(tp - current_tp) < tick_size * 0.1)
      {
         target_warning = false;
         continue;
      }

      MqlTick quote;
      const double distance = MathMax(
         (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL),
         (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL)) * _Point + tick_size;
      if(!SymbolInfoTick(_Symbol, quote) ||
         !MarketStopsValid(buy, quote.bid, quote.ask, sl, tp, distance))
      {
         WarnTargetOnce("stop/freeze distance prevents adjustment");
         continue;
      }
      if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED) ||
         !AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) || !AccountInfoInteger(ACCOUNT_TRADE_EXPERT))
      {
         WarnTargetOnce("automated trading unavailable");
         continue;
      }

      // Keep the original SL; only align TP to the actual (possibly weighted) fill.
      const bool modified = trade.PositionModify(ticket, sl, tp);
      const uint code = trade.ResultRetcode();
      if(!modified || (code != TRADE_RETCODE_DONE && code != TRADE_RETCODE_NO_CHANGES))
      {
         WarnTargetOnce(trade.ResultRetcodeDescription());
         continue;
      }
      target_warning = false;
      PrintFormat("Position #%I64u TP aligned to actual fill %.8f: SL %.8f TP %.8f",
                  ticket, entry, sl, tp);
   }
   if(!found)
      target_warning = false;
}

void SubmitSignal(const bool buy, const MqlRates &signal, const double atr)
{
   if(HasSymbolExposure() || !TradingAllowed(buy))
      return;

   MqlTick quote;
   if(!SymbolInfoTick(_Symbol, quote) || !MathIsValidNumber(quote.bid) ||
      !MathIsValidNumber(quote.ask) || quote.bid <= 0 || quote.ask < quote.bid)
      return;
   const double spread = quote.ask - quote.bid;
   if(spread > InpMaxSpreadPrice)
   {
      Print("Signal skipped: spread exceeds limit.");
      return;
   }

   const double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double entry, sl, tp;
   if(!MarketLevels(buy, signal.high, signal.low, atr, quote.bid, quote.ask, tick_size,
                    InpSLBufferATR, InpRewardRisk, entry, sl, tp))
      return;
   const int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   entry = NormalizeDouble(entry, digits);
   sl = NormalizeDouble(sl, digits);
   tp = NormalizeDouble(tp, digits);

   const double min_distance = MathMax(tick_size,
      (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point);
   if(!MarketStopsValid(buy, quote.bid, quote.ask, sl, tp, min_distance))
   {
      Print("Signal skipped: current market price invalidates SL/TP or broker stop distance too large.");
      return;
   }

   const ENUM_ORDER_TYPE side = buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   const double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   const double max_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   const double lot_step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   const double volume = FixedVolume(InpFixedLots, min_lot, max_lot, lot_step);
   if(volume <= 0)
   {
      Print("Signal skipped: fixed lots incompatible with broker min/max/step. Lot unchanged.");
      return;
   }
   double stop_profit = 0;
   if(!OrderCalcProfit(side, _Symbol, volume, entry, sl, stop_profit) ||
      !MathIsValidNumber(stop_profit) || stop_profit >= 0)
   {
      Print("Signal skipped: cannot estimate stop-loss amount.");
      return;
   }
   double margin = 0;
   if(!OrderCalcMargin(side, _Symbol, volume, entry, margin) ||
      !MathIsValidNumber(margin) || margin < 0 ||
      margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.90)
   {
      Print("Signal skipped: insufficient free margin.");
      return;
   }

   if(!trade.SetTypeFillingBySymbol(_Symbol))
   {
      Print("Signal skipped: unsupported market filling policy.");
      return;
   }
   const bool sent = buy
      ? trade.Buy(volume, _Symbol, entry, sl, tp, MARKET_COMMENT)
      : trade.Sell(volume, _Symbol, entry, sl, tp, MARKET_COMMENT);
   const uint code = trade.ResultRetcode();
   if(!sent || (code != TRADE_RETCODE_DONE && code != TRADE_RETCODE_DONE_PARTIAL &&
                code != TRADE_RETCODE_PLACED))
   {
      PrintFormat("Order not confirmed: %u %s. No automatic resend.", code,
                  trade.ResultRetcodeDescription());
      return;
   }
   PrintFormat("%s market request accepted: order #%I64u deal #%I64u code=%u lots=%.8f quoted entry=%.*f SL=%.*f TP=%.*f estimated SL loss before costs=%.2f %s",
               buy ? "BUY" : "SELL", trade.ResultOrder(), trade.ResultDeal(), code, volume, digits, entry,
               digits, sl, digits, tp, -stop_profit,
               AccountInfoString(ACCOUNT_CURRENCY));
   // An accepted/partial request is never resent; reconcile the position when visible.
   last_target_sync = 0;
   AlignTakeProfit();
}

// False means data is not ready; retry only during the short new-bar window.
bool EvaluateClosedBar(const datetime bar_open)
{
   const int needed = InpUseConsolidation ? InpConsolidationBars + 1 : 1;
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, _Period, 1, needed, rates) != needed)
      return false;
   if(rates[0].time + PeriodSeconds(_Period) != bar_open)
   {
      Print("Signal skipped: preceding candle is separated by a session/data gap.");
      return true;
   }

   double atr, ema = 0;
   if(!ReadIndicator(atr_handle, InpATRPeriod, atr) ||
      (InpUseEMA && !ReadIndicator(ema_handle, InpEMAPeriod, ema)))
      return false;

   bool buy = false;
   const double min_body = (_Period == PERIOD_M5 ? InpM5BodyPips : InpM15BodyPips) * InpGoldPipSize;
   if(!MomentumSignal(rates[0].open, rates[0].high, rates[0].low, rates[0].close,
                      min_body, InpMaxWickPct, InpConservativeWick, buy) ||
      rates[0].high - rates[0].low > InpMaxCandleATR * atr)
      return true;
   if(InpUseEMA && (buy ? rates[0].close <= ema : rates[0].close >= ema))
      return true;
   if(InpUseConsolidation)
   {
      const double body = MathAbs(rates[0].close - rates[0].open);
      for(int i = 1; i < needed; ++i)
         if(MathAbs(rates[i].close - rates[i].open) >= body)
            return true;
   }
   SubmitSignal(buy, rates[0], atr);
   return true;
}

void OnTick()
{
   AlignTakeProfit();
   const datetime bar_open = iTime(_Symbol, _Period, 0);
   if(bar_open <= 0 || bar_open == last_processed_bar)
      return;
   if(last_processed_bar == 0)
   {
      last_processed_bar = bar_open;
      return;
   }
   if(TimeCurrent() - bar_open > InpMaxSignalDelaySeconds)
   {
      last_processed_bar = bar_open;
      return;
   }
   if(EvaluateClosedBar(bar_open))
      last_processed_bar = bar_open;
}
#endif
