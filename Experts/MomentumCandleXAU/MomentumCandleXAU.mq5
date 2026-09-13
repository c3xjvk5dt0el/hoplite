#ifndef MOMENTUM_CORE_TEST
#property copyright "Momentum Candle XAU"
#property version   "1.02"
#property strict
#property description "Closed-bar XAUUSD M5/M15 momentum breakout. Demo-test before live use."

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

bool MomentumLevels(const bool buy, const double high, const double low,
                    const double atr, const double spread, const double tick,
                    const double entry_atr, const double stop_atr,
                    const double reward_risk,
                    double &entry, double &sl, double &tp)
{
   if(!MathIsValidNumber(high) || !MathIsValidNumber(low) || !MathIsValidNumber(atr) ||
      !MathIsValidNumber(spread) || !MathIsValidNumber(tick) || !MathIsValidNumber(entry_atr) ||
      !MathIsValidNumber(stop_atr) || !MathIsValidNumber(reward_risk))
      return false;
   if(high <= low || low <= 0.0 || atr <= 0.0 || spread < 0.0 ||
      tick <= 0.0 || entry_atr < 0.0 || stop_atr < 0.0 || reward_risk <= 0.0)
      return false;

   const double entry_buffer = MathMax(atr * entry_atr, tick);
   const double stop_buffer = MathMax(atr * stop_atr, tick);
   // MT5 gold candles use Bid; buy triggers and short exits use Ask.
   if(buy)
   {
      entry = PriceUp(high + entry_buffer + spread, tick);
      sl = PriceDown(low - stop_buffer, tick);
      tp = PriceUp(entry + reward_risk * (entry - sl), tick);
   }
   else
   {
      entry = PriceDown(low - entry_buffer, tick);
      sl = PriceUp(high + stop_buffer + spread, tick);
      tp = PriceDown(entry - reward_risk * (sl - entry), tick);
   }
   return MathIsValidNumber(entry) && MathIsValidNumber(sl) && MathIsValidNumber(tp) &&
          entry > 0.0 && sl > 0.0 && tp > 0.0 &&
          (buy ? (sl < entry && tp > entry) : (tp < entry && sl > entry));
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
input double InpEntryBufferATR = 0.10;
input double InpSLBufferATR = 0.15;
input double InpRewardRisk = 2.0;
input int    InpPendingBars = 3;
input int    InpMaxSignalDelaySeconds = 30;

input group "Fixed lot and execution"
input double InpFixedLots = 0.01;
input double InpMaxSpreadPrice = 0.50;
input ulong  InpMagic = 26091301;

CTrade trade;
int atr_handle = INVALID_HANDLE;
int ema_handle = INVALID_HANDLE;
datetime last_processed_bar = 0;

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
      InpEntryBufferATR < 0 || InpSLBufferATR < 0 || InpRewardRisk < 1 ||
      InpPendingBars < 1 || InpPendingBars > 100 ||
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
   const long expiry = SymbolInfoInteger(_Symbol, SYMBOL_EXPIRATION_MODE);
   if((modes & SYMBOL_ORDER_STOP) == 0 || (modes & SYMBOL_ORDER_SL) == 0 ||
      (modes & SYMBOL_ORDER_TP) == 0 || (expiry & SYMBOL_EXPIRATION_SPECIFIED) == 0 ||
      SymbolInfoInteger(_Symbol, SYMBOL_CHART_MODE) != SYMBOL_CHART_MODE_BID ||
      SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE) <= 0)
   {
      Print("Broker must support Bid candles, stop orders, SL/TP and server-side specified expiry.");
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
   // Pending orders require RETURN independently of the market filling mode.
   trade.SetTypeFilling(ORDER_FILLING_RETURN);
   trade.SetMarginMode();
   last_processed_bar = iTime(_Symbol, _Period, 0);
   PrintFormat("Ready. Fixed lots=%.8f, no equity-based sizing. Waiting for next closed candle.", InpFixedLots);
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

void SubmitSignal(const bool buy, const MqlRates &signal, const double atr,
                  const datetime bar_open)
{
   if(HasSymbolExposure() || !TradingAllowed(buy))
      return;

   MqlTick quote;
   if(!SymbolInfoTick(_Symbol, quote) || quote.bid <= 0 || quote.ask < quote.bid)
      return;
   const double spread = quote.ask - quote.bid;
   if(spread > InpMaxSpreadPrice)
   {
      Print("Signal skipped: spread exceeds limit.");
      return;
   }

   const double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double entry, sl, tp;
   if(!MomentumLevels(buy, signal.high, signal.low, atr, spread, tick_size,
                      InpEntryBufferATR, InpSLBufferATR, InpRewardRisk, entry, sl, tp))
      return;
   const int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   entry = NormalizeDouble(entry, digits);
   sl = NormalizeDouble(sl, digits);
   tp = NormalizeDouble(tp, digits);

   const double min_distance = MathMax(tick_size,
      (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point);
   const double market_distance = buy ? entry - quote.ask : quote.bid - entry;
   if(market_distance < min_distance || MathAbs(entry - sl) < min_distance ||
      MathAbs(tp - entry) < min_distance)
   {
      Print("Signal skipped: breakout already passed or broker stop distance too large.");
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

   const datetime expiration = bar_open + InpPendingBars * PeriodSeconds(_Period);
   if(expiration <= TimeCurrent())
      return;
   const bool sent = buy
      ? trade.BuyStop(volume, entry, _Symbol, sl, tp, ORDER_TIME_SPECIFIED, expiration, "MomentumXAU")
      : trade.SellStop(volume, entry, _Symbol, sl, tp, ORDER_TIME_SPECIFIED, expiration, "MomentumXAU");
   const uint code = trade.ResultRetcode();
   if(!sent || (code != TRADE_RETCODE_DONE && code != TRADE_RETCODE_PLACED) ||
      trade.ResultOrder() == 0)
   {
      PrintFormat("Order not confirmed: %u %s. No automatic resend.", code,
                  trade.ResultRetcodeDescription());
      return;
   }
   PrintFormat("%s stop #%I64u fixed lots=%.8f entry=%.*f SL=%.*f TP=%.*f estimated SL loss before costs=%.2f %s expires=%s",
               buy ? "BUY" : "SELL", trade.ResultOrder(), volume, digits, entry,
               digits, sl, digits, tp, -stop_profit,
               AccountInfoString(ACCOUNT_CURRENCY), TimeToString(expiration));
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
   SubmitSignal(buy, rates[0], atr, bar_open);
   return true;
}

void OnTick()
{
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
