#ifndef PULLBACK_CORE_TEST
#property copyright "Trend Pullback XAU"
#property version   "1.00"
#property strict
#property description "Closed-bar XAUUSD M5 EMA pullback with completed M15 trend confirmation."

#include <Trade\Trade.mqh>
#endif

bool PullbackSignal(const double open, const double high, const double low,
                    const double close, const double ema, bool &buy)
{
   if(!MathIsValidNumber(open) || !MathIsValidNumber(high) || !MathIsValidNumber(low) ||
      !MathIsValidNumber(close) || !MathIsValidNumber(ema) ||
      low <= 0.0 || ema <= 0.0 || high < MathMax(open, close) ||
      low > MathMin(open, close) || high < low)
      return false;

   if(low <= ema && close > ema && close > open)
   {
      buy = true;
      return true;
   }
   if(high >= ema && close < ema && close < open)
   {
      buy = false;
      return true;
   }
   return false;
}

double PriceUp(const double price, const double tick)
{
   return MathCeil(price / tick - 1e-9) * tick;
}

double PriceDown(const double price, const double tick)
{
   return MathFloor(price / tick + 1e-9) * tick;
}

// Formula: buy=min(last three M5 lows)-0.10*ATR; sell=max(highs)+0.10*ATR+spread.
bool PullbackSwingStop(const bool buy,
                       const double high1, const double low1,
                       const double high2, const double low2,
                       const double high3, const double low3,
                       const double atr, const double spread, const double tick,
                       double &sl)
{
   if(!MathIsValidNumber(high1) || !MathIsValidNumber(low1) ||
      !MathIsValidNumber(high2) || !MathIsValidNumber(low2) ||
      !MathIsValidNumber(high3) || !MathIsValidNumber(low3) ||
      !MathIsValidNumber(atr) || !MathIsValidNumber(spread) || !MathIsValidNumber(tick) ||
      low1 <= 0.0 || low2 <= 0.0 || low3 <= 0.0 || atr <= 0.0 || spread < 0.0 || tick <= 0.0 ||
      high1 < low1 || high2 < low2 || high3 < low3)
      return false;

   const double buffer = MathMax(0.10 * atr, tick);
   sl = buy ? PriceDown(MathMin(low1, MathMin(low2, low3)) - buffer, tick)
            : PriceUp(MathMax(high1, MathMax(high2, high3)) + buffer + spread, tick);
   return MathIsValidNumber(sl) && sl > 0.0;
}

bool CurrentQuote(const bool buy, const double bid, const double ask, double &entry)
{
   if(!MathIsValidNumber(bid) || !MathIsValidNumber(ask) || bid <= 0.0 || ask < bid)
      return false;
   entry = buy ? ask : bid;
   return MathIsValidNumber(entry) && entry > 0.0;
}

bool TargetFromEntry(const bool buy, const double entry, const double sl,
                     const double tick, const double reward_risk, double &tp)
{
   if(!MathIsValidNumber(entry) || !MathIsValidNumber(sl) || !MathIsValidNumber(tick) ||
      !MathIsValidNumber(reward_risk) || entry <= 0.0 || sl <= 0.0 || tick <= 0.0 ||
      reward_risk <= 0.0)
      return false;
   const double risk = buy ? entry - sl : sl - entry;
   if(risk <= 0.0)
      return false;
   tp = buy ? PriceUp(entry + reward_risk * risk, tick)
            : PriceDown(entry - reward_risk * risk, tick);
   return MathIsValidNumber(tp) && tp > 0.0 && (buy ? tp > entry : tp < entry);
}

bool SpreadRatioAllowed(const double spread, const double entry, const double sl,
                        const double max_spread_price, const double max_spread_risk_pct)
{
   if(!MathIsValidNumber(spread) || !MathIsValidNumber(entry) || !MathIsValidNumber(sl) ||
      !MathIsValidNumber(max_spread_price) || !MathIsValidNumber(max_spread_risk_pct) ||
      spread < 0.0 || entry <= 0.0 || sl <= 0.0 || max_spread_price < 0.0 ||
      max_spread_risk_pct < 0.0)
      return false;
   const double risk = MathAbs(entry - sl);
   return risk > 0.0 && spread <= max_spread_price &&
          spread <= (max_spread_risk_pct / 100.0) * risk;
}

double FixedVolume(const double requested, const double min_lot,
                   const double max_lot, const double step)
{
   if(!MathIsValidNumber(requested) || !MathIsValidNumber(min_lot) ||
      !MathIsValidNumber(max_lot) || !MathIsValidNumber(step) || requested <= 0.0 ||
      min_lot <= 0.0 || max_lot < min_lot || step <= 0.0 || requested < min_lot ||
      requested > max_lot)
      return 0.0;

   const double volume = NormalizeDouble(requested, 8);
   const double grid_volume = MathFloor(volume / step + 0.5) * step;
   // Fixed volume is rejected, never rounded to a broker-supported lot size.
   if(volume <= 0.0 || MathAbs(volume - requested) > 1e-10 ||
      MathAbs(grid_volume - volume) > 1e-10)
      return 0.0;
   return volume;
}

bool TimeExpired(const long opened_at, const long now, const int max_hold_minutes)
{
   return opened_at > 0 && now >= opened_at && max_hold_minutes > 0 &&
          now - opened_at >= (long)max_hold_minutes * 60;
}

bool SignalWindowOpen(const long bar_open, const long now, const int max_delay_seconds)
{
   return bar_open > 0 && now >= bar_open && max_delay_seconds >= 0 &&
          now - bar_open <= max_delay_seconds;
}

bool CloseVolumeReflected(const double before, const double filled,
                          const double remaining, const double volume_step)
{
   if(!MathIsValidNumber(before) || !MathIsValidNumber(filled) ||
      !MathIsValidNumber(remaining) || !MathIsValidNumber(volume_step) ||
      before <= 0.0 || filled < 0.0 || remaining < 0.0 || volume_step <= 0.0)
      return false;
   return remaining <= MathMax(0.0, before - filled) + volume_step * 0.5;
}

bool MarketStopsValid(const bool buy, const double bid, const double ask,
                      const double sl, const double tp, const double distance)
{
   if(!MathIsValidNumber(bid) || !MathIsValidNumber(ask) || !MathIsValidNumber(sl) ||
      !MathIsValidNumber(tp) || !MathIsValidNumber(distance) || bid <= 0.0 || ask < bid ||
      sl <= 0.0 || tp <= 0.0 || distance <= 0.0)
      return false;
   return buy ? bid - sl >= distance && tp - bid >= distance
              : sl - ask >= distance && ask - tp >= distance;
}

// Local C++ tests compile these helpers directly; MT5 compiles the EA below.
#ifndef PULLBACK_CORE_TEST

input group "Trend Pullback XAU - execution"
input double InpFixedLots = 0.01;
input double InpRewardRisk = 1.5;
input double InpMaxSpreadPrice = 0.50;
input double InpMaxSpreadRiskPct = 10.0;
input int    InpMaxHoldMinutes = 60;
input ulong  InpDeviationPoints = 50;
input ulong  InpMagic = 26091320;

const int EMA_PERIOD = 20;
const int ATR_PERIOD = 14;
const int MAX_SIGNAL_DELAY_SECONDS = 30;
const string MARKET_COMMENT = "TrendPullbackXAU";

CTrade trade;
int m5_ema_handle = INVALID_HANDLE;
int m15_ema20_handle = INVALID_HANDLE;
int m15_ema50_handle = INVALID_HANDLE;
int atr_handle = INVALID_HANDLE;
datetime last_processed_bar = 0;
datetime last_target_sync = 0;
datetime last_target_warning = 0;
datetime last_timeout_close_time = 0;
ulong last_timeout_close_ticket = 0;
ulong pending_close_ticket = 0;
ulong pending_close_order = 0;
long pending_close_position_id = 0;
double pending_close_volume = 0.0;

void ReleaseIndicators()
{
   if(m5_ema_handle != INVALID_HANDLE)
      IndicatorRelease(m5_ema_handle);
   if(m15_ema20_handle != INVALID_HANDLE)
      IndicatorRelease(m15_ema20_handle);
   if(m15_ema50_handle != INVALID_HANDLE)
      IndicatorRelease(m15_ema50_handle);
   if(atr_handle != INVALID_HANDLE)
      IndicatorRelease(atr_handle);
   m5_ema_handle = INVALID_HANDLE;
   m15_ema20_handle = INVALID_HANDLE;
   m15_ema50_handle = INVALID_HANDLE;
   atr_handle = INVALID_HANDLE;
}

bool IsXauUsdSymbol()
{
   string name = _Symbol;
   StringToUpper(name);
   return (SymbolInfoString(_Symbol, SYMBOL_CURRENCY_BASE) == "XAU" &&
           SymbolInfoString(_Symbol, SYMBOL_CURRENCY_PROFIT) == "USD") ||
          StringFind(name, "XAUUSD") == 0;
}

bool ReadCompletedValue(const int handle, const int period, const int shift, double &value)
{
   if(handle == INVALID_HANDLE || period < 1 || shift < 1 ||
      BarsCalculated(handle) < period + shift + 1)
      return false;
   double values[];
   if(CopyBuffer(handle, 0, shift, 1, values) != 1 || !MathIsValidNumber(values[0]) ||
      values[0] == EMPTY_VALUE || values[0] <= 0.0)
      return false;
   value = values[0];
   return true;
}

bool IsOwnedPositionSelected()
{
   return PositionGetString(POSITION_SYMBOL) == _Symbol &&
          (ulong)PositionGetInteger(POSITION_MAGIC) == InpMagic &&
          PositionGetString(POSITION_COMMENT) == MARKET_COMMENT;
}

bool HasSymbolExposure()
{
   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      const ulong ticket = PositionGetTicket(i);
      if(ticket != 0 && PositionSelectByTicket(ticket) && PositionGetString(POSITION_SYMBOL) == _Symbol)
         return true;
   }
   for(int i = OrdersTotal() - 1; i >= 0; --i)
   {
      const ulong ticket = OrderGetTicket(i);
      if(ticket != 0 && OrderSelect(ticket) && OrderGetString(ORDER_SYMBOL) == _Symbol)
         return true;
   }
   return false;
}

double BrokerStopDistance(const bool include_freeze)
{
   const double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   const double tick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   const long stops = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   const long freeze = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   if(!MathIsValidNumber(point) || !MathIsValidNumber(tick) || point <= 0.0 || tick <= 0.0)
      return 0.0;
   const long constrained_points = include_freeze && freeze > stops ? freeze : stops;
   return MathMax(tick, (double)constrained_points * point) + tick;
}

bool AutomatedTradingAllowed()
{
   return TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) && MQLInfoInteger(MQL_TRADE_ALLOWED) &&
          AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) && AccountInfoInteger(ACCOUNT_TRADE_EXPERT);
}

bool TradingAllowed(const bool buy)
{
   if(!AutomatedTradingAllowed())
      return false;
   const long mode = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE);
   return mode == SYMBOL_TRADE_MODE_FULL ||
          (buy && mode == SYMBOL_TRADE_MODE_LONGONLY) ||
          (!buy && mode == SYMBOL_TRADE_MODE_SHORTONLY);
}

void WarnTargetThrottled(const string message)
{
   const datetime now = TimeCurrent();
   if(now <= 0 || (last_target_warning > 0 && now - last_target_warning < 60))
      return;
   last_target_warning = now;
   Print("TP alignment pending: ", message, ". Current broker SL/TP remains unchanged.");
}

void AlignTakeProfit()
{
   const datetime now = TimeCurrent();
   if(now <= 0 || now == last_target_sync)
      return;
   last_target_sync = now;

   MqlTick tick_data;
   if(!SymbolInfoTick(_Symbol, tick_data))
      return;
   const double tick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   const double distance = BrokerStopDistance(true);
   if(!MathIsValidNumber(tick) || tick <= 0.0 || distance <= 0.0)
      return;

   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      const ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket) || !IsOwnedPositionSelected())
         continue;
      const datetime opened_at = (datetime)PositionGetInteger(POSITION_TIME);
      // The time stop has priority over any protection amendment.
      if(TimeExpired((long)opened_at, (long)now, InpMaxHoldMinutes))
         continue;

      const long type = PositionGetInteger(POSITION_TYPE);
      const bool buy = type == POSITION_TYPE_BUY;
      if(type != POSITION_TYPE_BUY && type != POSITION_TYPE_SELL)
         continue;
      const double entry = PositionGetDouble(POSITION_PRICE_OPEN);
      const double sl = PositionGetDouble(POSITION_SL);
      const double existing_tp = PositionGetDouble(POSITION_TP);
      double desired_tp = 0.0;
      if(!TargetFromEntry(buy, entry, sl, tick, InpRewardRisk, desired_tp))
      {
         WarnTargetThrottled("invalid actual fill, SL, or tick size");
         continue;
      }
      if(MathAbs(existing_tp - desired_tp) <= tick * 0.5)
         continue;
      if(!MarketStopsValid(buy, tick_data.bid, tick_data.ask, sl, desired_tp, distance))
      {
         WarnTargetThrottled("broker stop/freeze distance prevents update");
         continue;
      }
      if(!AutomatedTradingAllowed())
      {
         WarnTargetThrottled("automated trading is disabled");
         continue;
      }

      const bool modified = trade.PositionModify(ticket, sl, desired_tp);
      const uint code = trade.ResultRetcode();
      if(!modified || (code != TRADE_RETCODE_DONE && code != TRADE_RETCODE_NO_CHANGES))
         WarnTargetThrottled(StringFormat("modify position #%I64u returned %u %s", ticket,
                             code, trade.ResultRetcodeDescription()));
   }
}

bool ReadCloseFilledVolume(double &filled)
{
   filled = 0.0;
   if(pending_close_position_id <= 0 || !HistorySelectByPosition(pending_close_position_id))
      return false;
   for(int i = 0; i < HistoryDealsTotal(); ++i)
   {
      const ulong deal = HistoryDealGetTicket(i);
      if(deal == 0)
         return false;
      if((ulong)HistoryDealGetInteger(deal, DEAL_ORDER) != pending_close_order ||
         HistoryDealGetInteger(deal, DEAL_POSITION_ID) != pending_close_position_id)
         continue;
      const long entry = HistoryDealGetInteger(deal, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY)
         return false;
      const double volume = HistoryDealGetDouble(deal, DEAL_VOLUME);
      if(!MathIsValidNumber(volume) || volume <= 0.0)
         return false;
      filled += volume;
   }
   return MathIsValidNumber(filled);
}

bool CloseInFlight(const ulong ticket)
{
   if(!PositionSelectByTicket(ticket))
      return false;
   const long position_id = PositionGetInteger(POSITION_IDENTIFIER);
   for(int i = OrdersTotal() - 1; i >= 0; --i)
   {
      const ulong order = OrderGetTicket(i);
      if(order != 0 && OrderSelect(order) && OrderGetString(ORDER_SYMBOL) == _Symbol &&
         OrderGetInteger(ORDER_POSITION_ID) == position_id)
         return true;
   }
   if(pending_close_ticket != ticket)
      return false;
   // No history yet is an unknown outcome, not permission to resend.
   if(pending_close_order == 0 || !HistoryOrderSelect(pending_close_order))
      return true;
   const long state = HistoryOrderGetInteger(pending_close_order, ORDER_STATE);
   if(state != ORDER_STATE_FILLED && state != ORDER_STATE_CANCELED &&
      state != ORDER_STATE_REJECTED && state != ORDER_STATE_EXPIRED)
      return true;
   const double requested = HistoryOrderGetDouble(pending_close_order, ORDER_VOLUME_INITIAL);
   const double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double filled = 0.0;
   // A canceled IOC remainder is not filled volume; use its actual close deals.
   if(!ReadCloseFilledVolume(filled) ||
      (state == ORDER_STATE_FILLED && (!MathIsValidNumber(requested) || requested <= 0.0 ||
                                       filled + step * 0.5 < requested)))
      return true;
   if(!PositionSelectByTicket(ticket))
      return false;
   if(!CloseVolumeReflected(pending_close_volume, filled, PositionGetDouble(POSITION_VOLUME),
                            SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP)))
      return true;
   pending_close_ticket = 0;
   pending_close_order = 0;
   pending_close_position_id = 0;
   pending_close_volume = 0.0;
   return false;
}

void CloseExpiredPositions()
{
   const datetime now = TimeCurrent();
   if(now <= 0 || !AutomatedTradingAllowed())
      return;
   if(pending_close_ticket != 0 && !PositionSelectByTicket(pending_close_ticket))
   {
      pending_close_ticket = 0;
      pending_close_order = 0;
      pending_close_position_id = 0;
      pending_close_volume = 0.0;
   }
   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      const ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket) || !IsOwnedPositionSelected())
         continue;
      if(!TimeExpired((long)PositionGetInteger(POSITION_TIME), (long)now, InpMaxHoldMinutes))
         continue;
      if(CloseInFlight(ticket) || !PositionSelectByTicket(ticket) || !IsOwnedPositionSelected())
         continue;
      if(ticket == last_timeout_close_ticket && now == last_timeout_close_time)
         continue;

      last_timeout_close_ticket = ticket;
      last_timeout_close_time = now;
      const double before_volume = PositionGetDouble(POSITION_VOLUME);
      const long position_id = PositionGetInteger(POSITION_IDENTIFIER);
      const bool closed = trade.PositionClose(ticket, InpDeviationPoints);
      const uint code = trade.ResultRetcode();
      if(code == TRADE_RETCODE_DONE || code == TRADE_RETCODE_DONE_PARTIAL ||
         code == TRADE_RETCODE_PLACED || code == TRADE_RETCODE_TIMEOUT)
      {
         pending_close_ticket = ticket;
         pending_close_order = trade.ResultOrder();
         pending_close_position_id = position_id;
         pending_close_volume = before_volume;
         if(pending_close_order == 0)
            PrintFormat("Close outcome uncertain for #%I64u; automatic resend blocked. Inspect positions/Journal; existing SL/TP remain.", ticket);
      }
      if(!closed || (code != TRADE_RETCODE_DONE && code != TRADE_RETCODE_DONE_PARTIAL &&
                     code != TRADE_RETCODE_PLACED))
         PrintFormat("%d-minute close not confirmed for position #%I64u: %u %s", InpMaxHoldMinutes,
                     ticket, code, trade.ResultRetcodeDescription());
   }
}

void SubmitSignal(const bool buy, const MqlRates &bars[], const double atr)
{
   if(HasSymbolExposure() || !TradingAllowed(buy))
      return;

   MqlTick quote;
   if(!SymbolInfoTick(_Symbol, quote))
      return;
   const double tick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double entry = 0.0, sl = 0.0, tp = 0.0;
   if(!CurrentQuote(buy, quote.bid, quote.ask, entry) ||
      !PullbackSwingStop(buy, bars[0].high, bars[0].low, bars[1].high, bars[1].low,
                         bars[2].high, bars[2].low, atr, quote.ask - quote.bid, tick, sl) ||
      !TargetFromEntry(buy, entry, sl, tick, InpRewardRisk, tp) ||
      !SpreadRatioAllowed(quote.ask - quote.bid, entry, sl, InpMaxSpreadPrice,
                          InpMaxSpreadRiskPct))
      return;

   // Freeze distance affects amendments; initial market orders require only the stops distance.
   const double distance = BrokerStopDistance(false);
   if(distance <= 0.0 || !MarketStopsValid(buy, quote.bid, quote.ask, sl, tp, distance))
      return;
   const double volume = FixedVolume(InpFixedLots, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN),
                                     SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX),
                                     SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP));
   if(volume <= 0.0)
   {
      PrintFormat("Fixed lots %.8f incompatible with broker min/max/step.", InpFixedLots);
      return;
   }

   double margin = 0.0;
   const double free_margin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   const ENUM_ORDER_TYPE order_type = buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   if(!OrderCalcMargin(order_type, _Symbol, volume, entry, margin) ||
      !MathIsValidNumber(margin) || !MathIsValidNumber(free_margin) || margin < 0.0 ||
      free_margin < 0.0 || margin > free_margin * 0.90)
   {
      Print("Signal skipped: insufficient free margin or margin estimate unavailable.");
      return;
   }
   const bool sent = buy ? trade.Buy(volume, _Symbol, entry, sl, tp, MARKET_COMMENT)
                         : trade.Sell(volume, _Symbol, entry, sl, tp, MARKET_COMMENT);
   const uint code = trade.ResultRetcode();
   if(!sent || (code != TRADE_RETCODE_DONE && code != TRADE_RETCODE_DONE_PARTIAL &&
                code != TRADE_RETCODE_PLACED))
   {
      PrintFormat("Order not confirmed: %u %s. No automatic resend.", code,
                  trade.ResultRetcodeDescription());
      return;
   }

   PrintFormat("%s accepted: order #%I64u deal #%I64u code=%u lots=%.8f quote=%.*f SL=%.*f TP=%.*f",
               buy ? "BUY" : "SELL", trade.ResultOrder(), trade.ResultDeal(), code, volume,
               (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS), entry,
               (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS), sl,
               (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS), tp);
   // A partial fill is accepted once, then its target is recalculated from its actual fill price.
   last_target_sync = 0;
   AlignTakeProfit();
}

// False only while bar/indicator data are not ready; then this same just-opened M5 bar may retry.
bool EvaluateClosedBar(const datetime current_bar_open)
{
   MqlRates bars[];
   ArraySetAsSeries(bars, true);
   if(CopyRates(_Symbol, PERIOD_M5, 1, 3, bars) != 3)
      return false;
   const int m5_seconds = PeriodSeconds(PERIOD_M5);
   if(m5_seconds <= 0 || bars[0].time + m5_seconds != current_bar_open ||
      bars[1].time + m5_seconds != bars[0].time || bars[2].time + m5_seconds != bars[1].time)
   {
      Print("Signal skipped: signal and three-bar swing window must be contiguous.");
      return true;
   }

   double m5_ema = 0.0, atr = 0.0, m15_ema20 = 0.0, m15_ema50_1 = 0.0, m15_ema50_4 = 0.0;
   // Every value deliberately reads a completed bar: M5 shift 1; M15 shifts 1 and 4.
   if(!ReadCompletedValue(m5_ema_handle, EMA_PERIOD, 1, m5_ema) ||
      !ReadCompletedValue(atr_handle, ATR_PERIOD, 1, atr) ||
      !ReadCompletedValue(m15_ema20_handle, EMA_PERIOD, 1, m15_ema20) ||
      !ReadCompletedValue(m15_ema50_handle, 50, 1, m15_ema50_1) ||
      !ReadCompletedValue(m15_ema50_handle, 50, 4, m15_ema50_4))
      return false;

   bool buy = false;
   if(!PullbackSignal(bars[0].open, bars[0].high, bars[0].low, bars[0].close, m5_ema, buy))
      return true;
   const bool m15_trend = buy ? (m15_ema20 > m15_ema50_1 && m15_ema50_1 > m15_ema50_4)
                               : (m15_ema20 < m15_ema50_1 && m15_ema50_1 < m15_ema50_4);
   if(!m15_trend)
      return true;

   SubmitSignal(buy, bars, atr);
   return true;
}

int OnInit()
{
   if(!IsXauUsdSymbol() || _Period != PERIOD_M5)
   {
      Print("Use an XAUUSD M5 chart (broker suffixes supported).");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(!MathIsValidNumber(InpFixedLots) || !MathIsValidNumber(InpRewardRisk) ||
      !MathIsValidNumber(InpMaxSpreadPrice) || !MathIsValidNumber(InpMaxSpreadRiskPct) ||
      InpFixedLots <= 0.0 || InpRewardRisk <= 0.0 || InpMaxSpreadPrice <= 0.0 ||
      InpMaxSpreadRiskPct <= 0.0 || InpMaxSpreadRiskPct > 100.0 || InpMaxHoldMinutes < 0 || InpDeviationPoints == 0 ||
      InpMagic == 0)
   {
      Print("Invalid inputs: positive finite lots/RR/spread, nonnegative hold duration, and nonzero magic required.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(FixedVolume(InpFixedLots, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN),
                  SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX),
                  SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP)) <= 0.0)
   {
      PrintFormat("Fixed lots %.8f incompatible with broker min/max/step.", InpFixedLots);
      return INIT_PARAMETERS_INCORRECT;
   }
   const long order_modes = SymbolInfoInteger(_Symbol, SYMBOL_ORDER_MODE);
   if((order_modes & SYMBOL_ORDER_MARKET) == 0 || (order_modes & SYMBOL_ORDER_SL) == 0 ||
      (order_modes & SYMBOL_ORDER_TP) == 0 ||
      SymbolInfoInteger(_Symbol, SYMBOL_CHART_MODE) != SYMBOL_CHART_MODE_BID ||
      SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE) <= 0.0)
   {
      Print("Broker must support Bid candles, market orders, and attached SL/TP.");
      return INIT_FAILED;
   }

   m5_ema_handle = iMA(_Symbol, PERIOD_M5, EMA_PERIOD, 0, MODE_EMA, PRICE_CLOSE);
   m15_ema20_handle = iMA(_Symbol, PERIOD_M15, EMA_PERIOD, 0, MODE_EMA, PRICE_CLOSE);
   m15_ema50_handle = iMA(_Symbol, PERIOD_M15, 50, 0, MODE_EMA, PRICE_CLOSE);
   atr_handle = iATR(_Symbol, PERIOD_M5, ATR_PERIOD);
   if(m5_ema_handle == INVALID_HANDLE || m15_ema20_handle == INVALID_HANDLE ||
      m15_ema50_handle == INVALID_HANDLE || atr_handle == INVALID_HANDLE)
   {
      Print("Unable to create EMA20/EMA50/ATR14 handles.");
      ReleaseIndicators();
      return INIT_FAILED;
   }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetAsyncMode(false);
   trade.SetMarginMode();
   trade.SetDeviationInPoints(InpDeviationPoints);
   if(!trade.SetTypeFillingBySymbol(_Symbol))
   {
      Print("Cannot determine a supported market filling policy.");
      ReleaseIndicators();
      return INIT_FAILED;
   }
   // Do not evaluate an already-forming/previous signal after attaching the EA.
   last_processed_bar = iTime(_Symbol, PERIOD_M5, 0);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   ReleaseIndicators();
}

void OnTick()
{
   CloseExpiredPositions();
   // Expired positions are deliberately skipped inside this function.
   AlignTakeProfit();

   const datetime current_bar_open = iTime(_Symbol, PERIOD_M5, 0);
   if(current_bar_open <= 0)
      return;
   if(last_processed_bar == 0)
   {
      // History was unavailable at init; begin only after the next completed M5 candle.
      last_processed_bar = current_bar_open;
      return;
   }
   if(current_bar_open == last_processed_bar)
      return;
   if(!SignalWindowOpen((long)current_bar_open, (long)TimeCurrent(), MAX_SIGNAL_DELAY_SECONDS))
   {
      last_processed_bar = current_bar_open;
      return;
   }
   if(EvaluateClosedBar(current_bar_open))
      last_processed_bar = current_bar_open;
}
#endif
