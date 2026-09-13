#ifndef SWEEP_CORE_TEST
#property copyright "Sweep Reclaim XAU"
#property version   "1.00"
#property strict
#property description "Locked descriptive fallback: completed-bar XAUUSD M5 sweep/reclaim with completed M15 trend confirmation."

#include <Trade\Trade.mqh>
#endif

const int SWEEP_PRECEDING_BARS = 24;
const int SWEEP_CLOSED_BARS = 25;
const int M5_ATR_PERIOD = 14;
const int M15_FAST_EMA_PERIOD = 20;
const int M15_SLOW_EMA_PERIOD = 50;
const int MAX_SIGNAL_DELAY_SECONDS = 30;
const int SECONDS_PER_DAY = 86400;

const double LOCKED_FIXED_LOTS = 0.01;
const double LOCKED_REWARD_RISK = 1.00;
const double LOCKED_MIN_STOP_ATR = 1.25;
const double MAX_STOP_ATR = 2.50;
const double MAX_STOP_PRICE = 15.00;
const double MAX_SPREAD_PRICE = 0.50;
const double MAX_SPREAD_RISK_FRACTION = 0.10;
const double ESTIMATED_ENTRY_SLIPPAGE_PRICE = 0.05;
const double ESTIMATED_STOP_SLIPPAGE_PRICE = 0.05;
const double ESTIMATED_ROUND_TRIP_COMMISSION_USD = 0.04;
const double DAILY_ENTRY_RISK_BUDGET_USD = 25.00;
const double REQUIRED_CONTRACT_SIZE_OZ = 100.0;
const int MAX_OPENING_ORDERS_PER_UTC_DAY = 12;

bool PositiveFinite(const double value)
{
   return MathIsValidNumber(value) && value > 0.0;
}

bool ValidHighLow(const double high, const double low)
{
   return PositiveFinite(high) && PositiveFinite(low) && high >= low;
}

bool ValidOhlc(const double open, const double high, const double low, const double close)
{
   return PositiveFinite(open) && PositiveFinite(high) && PositiveFinite(low) && PositiveFinite(close) &&
          low <= MathMin(open, close) && MathMax(open, close) <= high;
}

bool TrueRange(const double high, const double low, const double previous_close, double &range)
{
   range = 0.0;
   if(!ValidHighLow(high, low) || !PositiveFinite(previous_close))
      return false;
   range = MathMax(high, previous_close) - MathMin(low, previous_close);
   return MathIsValidNumber(range) && range >= 0.0;
}

bool SimpleAtrFromSum(const double true_range_sum, const int period, double &atr)
{
   atr = 0.0;
   if(!MathIsValidNumber(true_range_sum) || true_range_sum < 0.0 || period < 1)
      return false;
   atr = true_range_sum / period;
   return PositiveFinite(atr);
}

double PriceUp(const double price, const double tick)
{
   if(!PositiveFinite(price) || !PositiveFinite(tick))
      return 0.0;
   const double aligned = MathCeil(price / tick - 1e-9) * tick;
   return PositiveFinite(aligned) ? aligned : 0.0;
}

double PriceDown(const double price, const double tick)
{
   if(!PositiveFinite(price) || !PositiveFinite(tick))
      return 0.0;
   const double aligned = MathFloor(price / tick + 1e-9) * tick;
   return PositiveFinite(aligned) ? aligned : 0.0;
}

bool PreviousWindowSelected(const int copied_bars, const int signal_index,
                            const int first_preceding_index, const int last_preceding_index,
                            const int preceding_bars)
{
   return preceding_bars == SWEEP_PRECEDING_BARS && copied_bars == SWEEP_CLOSED_BARS &&
          signal_index == 0 && first_preceding_index == 1 &&
          last_preceding_index == SWEEP_PRECEDING_BARS;
}

bool AccumulateSweepBoundaries(const double high, const double low,
                               double &previous_low, double &previous_high)
{
   if(!ValidHighLow(high, low) || !PositiveFinite(previous_low) ||
      !PositiveFinite(previous_high) || previous_high < previous_low)
      return false;
   previous_low = MathMin(previous_low, low);
   previous_high = MathMax(previous_high, high);
   return PositiveFinite(previous_low) && PositiveFinite(previous_high) && previous_high >= previous_low;
}

bool SweepReclaimSignal(const double open, const double high, const double low, const double close,
                        const double previous_low, const double previous_high, bool &buy)
{
   buy = false;
   if(!ValidOhlc(open, high, low, close) || !PositiveFinite(previous_low) ||
      !PositiveFinite(previous_high) || previous_high < previous_low)
      return false;

   const double body = MathAbs(close - open);
   const double lower_wick = MathMin(open, close) - low;
   const double upper_wick = high - MathMax(open, close);
   if(close > open && lower_wick >= body && low < previous_low && close > previous_low)
   {
      buy = true;
      return true;
   }
   if(close < open && upper_wick >= body && high > previous_high && close < previous_high)
   {
      buy = false;
      return true;
   }
   return false;
}

bool CurrentQuote(const bool buy, const double bid, const double ask, double &entry)
{
   if(!PositiveFinite(bid) || !PositiveFinite(ask) || ask < bid)
      return false;
   entry = buy ? ask : bid;
   return PositiveFinite(entry);
}

bool SweepStop(const bool buy, const double signal_high, const double signal_low,
               const double atr, const double bid, const double ask, const double tick,
               const double min_stop_atr, double &entry, double &sl)
{
   entry = 0.0;
   sl = 0.0;
   if(!ValidHighLow(signal_high, signal_low) || !PositiveFinite(atr) || !PositiveFinite(tick) ||
      !PositiveFinite(min_stop_atr) || !CurrentQuote(buy, bid, ask, entry))
      return false;

   const double spread = ask - bid;
   const double buffer = MathMax(0.10 * atr, tick);
   if(!MathIsValidNumber(spread) || spread < 0.0 || !PositiveFinite(buffer))
      return false;

   if(buy)
   {
      const double raw_stop = signal_low - buffer;
      const double floor_stop = entry - min_stop_atr * atr;
      if(!PositiveFinite(raw_stop) || !PositiveFinite(floor_stop))
         return false;
      sl = PriceDown(MathMin(raw_stop, floor_stop), tick);
   }
   else
   {
      const double raw_stop = signal_high + buffer + spread;
      const double floor_stop = entry + min_stop_atr * atr;
      if(!PositiveFinite(raw_stop) || !PositiveFinite(floor_stop))
         return false;
      sl = PriceUp(MathMax(raw_stop, floor_stop), tick);
   }
   return PositiveFinite(sl) && (buy ? sl < entry : sl > entry);
}

bool QuotedStopRisk(const bool buy, const double entry, const double sl, double &risk)
{
   risk = 0.0;
   if(!PositiveFinite(entry) || !PositiveFinite(sl))
      return false;
   risk = buy ? entry - sl : sl - entry;
   return PositiveFinite(risk);
}

bool StopRiskWithinCaps(const bool buy, const double entry, const double sl, const double atr,
                        const double max_stop_atr, const double max_stop_price)
{
   if(!PositiveFinite(atr) || !PositiveFinite(max_stop_atr) || !PositiveFinite(max_stop_price))
      return false;
   double risk = 0.0;
   return QuotedStopRisk(buy, entry, sl, risk) && risk <= max_stop_atr * atr && risk <= max_stop_price;
}

bool SpreadRatioAllowed(const double spread, const double entry, const double sl,
                        const double max_spread_price, const double max_spread_risk_fraction)
{
   if(!MathIsValidNumber(spread) || !PositiveFinite(entry) || !PositiveFinite(sl) ||
      !MathIsValidNumber(max_spread_price) || !MathIsValidNumber(max_spread_risk_fraction) ||
      spread < 0.0 || max_spread_price < 0.0 || max_spread_risk_fraction < 0.0)
      return false;
   const double risk = MathAbs(entry - sl);
   return PositiveFinite(risk) && spread <= max_spread_price && spread <= max_spread_risk_fraction * risk;
}

bool TargetFromEntry(const bool buy, const double entry, const double sl,
                     const double tick, const double reward_risk, double &tp)
{
   tp = 0.0;
   if(!PositiveFinite(entry) || !PositiveFinite(sl) || !PositiveFinite(tick) ||
      !PositiveFinite(reward_risk))
      return false;
   double risk = 0.0;
   if(!QuotedStopRisk(buy, entry, sl, risk))
      return false;
   tp = buy ? PriceUp(entry + reward_risk * risk, tick)
            : PriceDown(entry - reward_risk * risk, tick);
   return PositiveFinite(tp) && (buy ? tp > entry : tp < entry);
}

double FixedVolume(const double requested, const double min_lot,
                   const double max_lot, const double step)
{
   if(!PositiveFinite(requested) || !PositiveFinite(min_lot) || !PositiveFinite(max_lot) ||
      !PositiveFinite(step) || max_lot < min_lot || requested < min_lot || requested > max_lot)
      return 0.0;

   const double volume = NormalizeDouble(requested, 8);
   const double grid_volume = MathFloor(volume / step + 0.5) * step;
   // Reject incompatible fixed lots instead of silently changing the requested exposure.
   if(!PositiveFinite(volume) || MathAbs(volume - requested) > 1e-10 ||
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
   if(!PositiveFinite(before) || !MathIsValidNumber(filled) || !MathIsValidNumber(remaining) ||
      !PositiveFinite(volume_step) || filled < 0.0 || remaining < 0.0)
      return false;
   return remaining <= MathMax(0.0, before - filled) + volume_step * 0.5;
}

bool MarketStopsValid(const bool buy, const double bid, const double ask,
                      const double sl, const double tp, const double distance)
{
   if(!PositiveFinite(bid) || !PositiveFinite(ask) || !PositiveFinite(sl) ||
      !PositiveFinite(tp) || !PositiveFinite(distance) || ask < bid)
      return false;
   return buy ? bid - sl >= distance && tp - bid >= distance
              : sl - ask >= distance && ask - tp >= distance;
}

bool EstimatedAdverseStopPrices(const bool buy, const double quote, const double sl,
                                const double entry_slippage, const double stop_slippage,
                                double &estimated_entry, double &estimated_stop_exit)
{
   estimated_entry = 0.0;
   estimated_stop_exit = 0.0;
   if(!PositiveFinite(quote) || !PositiveFinite(sl) || !MathIsValidNumber(entry_slippage) ||
      !MathIsValidNumber(stop_slippage) || entry_slippage < 0.0 || stop_slippage < 0.0 ||
      (buy ? sl >= quote : sl <= quote))
      return false;
   estimated_entry = buy ? quote + entry_slippage : quote - entry_slippage;
   estimated_stop_exit = buy ? sl - stop_slippage : sl + stop_slippage;
   return PositiveFinite(estimated_entry) && PositiveFinite(estimated_stop_exit) &&
          (buy ? estimated_entry > estimated_stop_exit : estimated_stop_exit > estimated_entry);
}

bool ValidUtcOffsetMinutes(const int offset_minutes)
{
   return offset_minutes >= -14 * 60 && offset_minutes <= 14 * 60;
}

bool BrokerTimeToUtc(const long broker_time, const int offset_minutes, long &utc_time)
{
   utc_time = 0;
   if(broker_time <= 0 || !ValidUtcOffsetMinutes(offset_minutes))
      return false;
   utc_time = broker_time - (long)offset_minutes * 60;
   return utc_time > 0;
}

bool ValidUtcSessionHours(const int start_hour, const int end_hour)
{
   return start_hour >= 0 && start_hour < 24 && end_hour > 0 && end_hour <= 24 &&
          start_hour < end_hour;
}

bool UtcEntrySessionOpen(const long broker_time, const int offset_minutes,
                         const int start_hour, const int end_hour)
{
   long utc_time = 0;
   if(!ValidUtcSessionHours(start_hour, end_hour) ||
      !BrokerTimeToUtc(broker_time, offset_minutes, utc_time))
      return false;
   const long day = utc_time / SECONDS_PER_DAY;
   const long seconds_into_day = utc_time % SECONDS_PER_DAY;
   const int weekday = (int)((day + 3) % 7); // Unix day zero was Thursday.
   const int hour = (int)(seconds_into_day / 3600);
   return weekday >= 0 && weekday < 5 && hour >= start_hour && hour < end_hour;
}

bool UtcDayBrokerStart(const long broker_time, const int offset_minutes, long &broker_day_start)
{
   broker_day_start = 0;
   long utc_time = 0;
   if(!BrokerTimeToUtc(broker_time, offset_minutes, utc_time))
      return false;
   const long utc_day_start = utc_time - utc_time % SECONDS_PER_DAY;
   broker_day_start = utc_day_start + (long)offset_minutes * 60;
   return broker_day_start > 0 && broker_day_start <= broker_time;
}

bool DailyEntryLimitAllowed(const int opening_orders, const int max_opening_orders)
{
   return opening_orders >= 0 && max_opening_orders > 0 && opening_orders < max_opening_orders;
}

bool DailyRiskBudgetAllowed(const double today_net, const double estimated_stop_loss,
                            const double daily_loss_budget)
{
   return MathIsValidNumber(today_net) && MathIsValidNumber(estimated_stop_loss) &&
          PositiveFinite(daily_loss_budget) && estimated_stop_loss >= 0.0 &&
          today_net - estimated_stop_loss >= -daily_loss_budget;
}

bool M15WarmupReady(const int available_bars, const int fast_calculated, const int slow_calculated)
{
   // 201 completed M15 bars plus the developing bar, matching the research warmup.
   return available_bars >= 202 && fast_calculated >= 202 && slow_calculated >= 202;
}

bool AccountModeAllowed(const bool demo_account, const bool real_account,
                        const bool allow_live_trading, const bool tester)
{
   return tester || demo_account || (real_account && allow_live_trading);
}

// Local C++ tests compile these helpers directly; MT5 compiles the EA below.
#ifndef SWEEP_CORE_TEST

input group "Sweep Reclaim XAU - locked fallback"
input double InpFixedLots = 0.01;
input double InpRewardRisk = 1.0;
input bool InpAllowLiveTrading = false;
input ulong InpMagic = 26091330;
input ulong InpDeviationPoints = 50;

input group "UTC/session and timing"
input int InpBrokerUtcOffsetMinutes = 0;
input int InpSessionStartUtcHour = 7;
input int InpSessionEndUtcHour = 18;
input int InpMaxHoldMinutes = 45;
input int InpMaxSignalDelaySeconds = 30;

const string MARKET_COMMENT = "SweepReclaimXAU";

CTrade trade;
int m15_ema20_handle = INVALID_HANDLE;
int m15_ema50_handle = INVALID_HANDLE;
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
   if(m15_ema20_handle != INVALID_HANDLE)
      IndicatorRelease(m15_ema20_handle);
   if(m15_ema50_handle != INVALID_HANDLE)
      IndicatorRelease(m15_ema50_handle);
   m15_ema20_handle = INVALID_HANDLE;
   m15_ema50_handle = INVALID_HANDLE;
}

bool IsXauUsdSymbol()
{
   string symbol_name = _Symbol;
   string base_currency = SymbolInfoString(_Symbol, SYMBOL_CURRENCY_BASE);
   string profit_currency = SymbolInfoString(_Symbol, SYMBOL_CURRENCY_PROFIT);
   StringToUpper(symbol_name);
   StringToUpper(base_currency);
   StringToUpper(profit_currency);
   return StringFind(symbol_name, "XAUUSD") == 0 && base_currency == "XAU" && profit_currency == "USD";
}

bool IsUsdAccount()
{
   string account_currency = AccountInfoString(ACCOUNT_CURRENCY);
   StringToUpper(account_currency);
   return account_currency == "USD";
}

bool HasRequiredContractSize()
{
   const double contract_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   return PositiveFinite(contract_size) && MathAbs(contract_size - REQUIRED_CONTRACT_SIZE_OZ) <= 1e-8;
}

bool ReadCompletedValue(const int handle, const int period, const int shift, double &value)
{
   if(handle == INVALID_HANDLE || period < 1 || shift < 1 ||
      BarsCalculated(handle) < period + shift + 1)
      return false;
   double values[];
   if(CopyBuffer(handle, 0, shift, 1, values) != 1 || !PositiveFinite(values[0]) ||
      values[0] == EMPTY_VALUE)
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
   if(!PositiveFinite(point) || !PositiveFinite(tick))
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
   Print("Nonconforming TP alignment: ", message,
         ". Current broker SL/TP remains unchanged; actual RR is not guaranteed 1:1 until corrected.");
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
   if(!PositiveFinite(tick) || distance <= 0.0)
      return;

   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      const ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket) || !IsOwnedPositionSelected())
         continue;
      const datetime opened_at = (datetime)PositionGetInteger(POSITION_TIME);
      // A timeout close always takes priority over a protection amendment.
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
      if(!PositiveFinite(volume))
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
   // A canceled IOC remainder is not filled volume; use actual close deals.
   if(!ReadCloseFilledVolume(filled) ||
      (state == ORDER_STATE_FILLED && (!PositiveFinite(requested) ||
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

bool EntryOrderAlreadyCounted(const ulong order, const ulong &orders[])
{
   for(int i = 0; i < ArraySize(orders); ++i)
      if(orders[i] == order)
         return true;
   return false;
}

bool ReadTodayStats(const datetime broker_now, int &opening_orders, double &today_net)
{
   opening_orders = 0;
   today_net = 0.0;
   long broker_day_start_long = 0;
   if(!UtcDayBrokerStart((long)broker_now, InpBrokerUtcOffsetMinutes, broker_day_start_long))
      return false;
   const datetime broker_day_start = (datetime)broker_day_start_long;
   // The upper bound is the current broker timestamp, never a future day boundary.
   if(broker_day_start > broker_now || !HistorySelect(broker_day_start, broker_now))
      return false;

   ulong entry_orders[];
   ArrayResize(entry_orders, 0);
   const int total = HistoryDealsTotal();
   if(total < 0)
      return false;
   for(int i = 0; i < total; ++i)
   {
      const ulong deal = HistoryDealGetTicket(i);
      if(deal == 0)
         return false;
      long raw_time = 0;
      long deal_magic = 0;
      string deal_symbol = "";
      if(!HistoryDealGetInteger(deal, DEAL_TIME, raw_time) ||
         !HistoryDealGetInteger(deal, DEAL_MAGIC, deal_magic) ||
         !HistoryDealGetString(deal, DEAL_SYMBOL, deal_symbol))
         return false;
      const datetime deal_time = (datetime)raw_time;
      if(deal_time < broker_day_start || deal_time > broker_now)
         return false;
      if(deal_symbol != _Symbol || deal_magic < 0 || (ulong)deal_magic != InpMagic)
         continue;

      double profit = 0.0;
      double swap = 0.0;
      double commission = 0.0;
      double fee = 0.0;
      if(!HistoryDealGetDouble(deal, DEAL_PROFIT, profit) ||
         !HistoryDealGetDouble(deal, DEAL_SWAP, swap) ||
         !HistoryDealGetDouble(deal, DEAL_COMMISSION, commission) ||
         !HistoryDealGetDouble(deal, DEAL_FEE, fee))
         return false;
      if(!MathIsValidNumber(profit) || !MathIsValidNumber(swap) ||
         !MathIsValidNumber(commission) || !MathIsValidNumber(fee))
         return false;
      today_net += profit + swap + commission + fee;
      if(!MathIsValidNumber(today_net))
         return false;

      long entry_type = 0;
      if(!HistoryDealGetInteger(deal, DEAL_ENTRY, entry_type))
         return false;
      if(entry_type != DEAL_ENTRY_IN && entry_type != DEAL_ENTRY_INOUT)
         continue;
      long raw_order = 0;
      if(!HistoryDealGetInteger(deal, DEAL_ORDER, raw_order) || raw_order <= 0)
         return false;
      const ulong order = (ulong)raw_order;
      if(!EntryOrderAlreadyCounted(order, entry_orders))
      {
         const int next_size = ArrayResize(entry_orders, ArraySize(entry_orders) + 1);
         if(next_size != ArraySize(entry_orders))
            return false;
         entry_orders[next_size - 1] = order;
      }
   }
   opening_orders = ArraySize(entry_orders);
   return opening_orders >= 0 && MathIsValidNumber(today_net);
}

bool EstimateStopLossUSD(const bool buy, const double quote, const double sl,
                         const double volume, double &estimated_stop_loss)
{
   estimated_stop_loss = 0.0;
   double estimated_entry = 0.0;
   double estimated_stop_exit = 0.0;
   if(!PositiveFinite(volume) ||
      !EstimatedAdverseStopPrices(buy, quote, sl, ESTIMATED_ENTRY_SLIPPAGE_PRICE,
                                  ESTIMATED_STOP_SLIPPAGE_PRICE,
                                  estimated_entry, estimated_stop_exit))
      return false;

   double profit = 0.0;
   const ENUM_ORDER_TYPE order_type = buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   if(!OrderCalcProfit(order_type, _Symbol, volume, estimated_entry, estimated_stop_exit, profit) ||
      !MathIsValidNumber(profit) || profit >= 0.0)
      return false;
   estimated_stop_loss = -profit + ESTIMATED_ROUND_TRIP_COMMISSION_USD;
   return PositiveFinite(estimated_stop_loss);
}

void SubmitSignal(const bool buy, const MqlRates &signal, const double atr)
{
   if(HasSymbolExposure() || !TradingAllowed(buy))
      return;

   const datetime broker_now = TimeCurrent();
   if(!UtcEntrySessionOpen((long)broker_now, InpBrokerUtcOffsetMinutes,
                           InpSessionStartUtcHour, InpSessionEndUtcHour))
      return;

   MqlTick quote;
   if(!SymbolInfoTick(_Symbol, quote))
      return;
   const double tick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double entry = 0.0;
   double sl = 0.0;
   double tp = 0.0;
   if(!SweepStop(buy, signal.high, signal.low, atr, quote.bid, quote.ask, tick,
                 LOCKED_MIN_STOP_ATR, entry, sl) ||
      !StopRiskWithinCaps(buy, entry, sl, atr, MAX_STOP_ATR, MAX_STOP_PRICE) ||
      !SpreadRatioAllowed(quote.ask - quote.bid, entry, sl, MAX_SPREAD_PRICE,
                          MAX_SPREAD_RISK_FRACTION) ||
      !TargetFromEntry(buy, entry, sl, tick, InpRewardRisk, tp))
      return;

   // Initial market orders need the broker stops level; the freeze level is for later TP alignment.
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

   int opening_orders = 0;
   double today_net = 0.0;
   if(!ReadTodayStats(broker_now, opening_orders, today_net))
   {
      Print("Signal skipped: UTC-day history is unavailable or incomplete.");
      return;
   }
   if(!DailyEntryLimitAllowed(opening_orders, MAX_OPENING_ORDERS_PER_UTC_DAY))
   {
      PrintFormat("Signal skipped: %d opening orders already recorded for this UTC day.", opening_orders);
      return;
   }
   double estimated_stop_loss = 0.0;
   if(!EstimateStopLossUSD(buy, entry, sl, volume, estimated_stop_loss))
   {
      Print("Signal skipped: unable to estimate adverse stop loss in USD.");
      return;
   }
   if(!DailyRiskBudgetAllowed(today_net, estimated_stop_loss, DAILY_ENTRY_RISK_BUDGET_USD))
   {
      PrintFormat("Signal skipped: UTC realized net %.2f minus estimated stop loss %.2f exceeds the USD %.2f entry-risk budget.",
                  today_net, estimated_stop_loss, DAILY_ENTRY_RISK_BUDGET_USD);
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

   PrintFormat("%s accepted: order #%I64u deal #%I64u code=%u lots=%.8f quote=%.*f SL=%.*f TP=%.*f estimatedSLloss=%.2f",
               buy ? "BUY" : "SELL", trade.ResultOrder(), trade.ResultDeal(), code, volume,
               (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS), entry,
               (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS), sl,
               (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS), tp, estimated_stop_loss);
   // A partial fill is accepted once, then TP is recalculated from its actual fill price.
   last_target_sync = 0;
   AlignTakeProfit();
}

bool ReadM5Atr14(const MqlRates &bars[], double &atr)
{
   atr = 0.0;
   if(ArraySize(bars) < M5_ATR_PERIOD + 1)
      return false;
   double sum = 0.0;
   // In series order, bars[0] is the signal and bars[1] supplies its prior close.
   for(int i = 0; i < M5_ATR_PERIOD; ++i)
   {
      double range = 0.0;
      if(!TrueRange(bars[i].high, bars[i].low, bars[i + 1].close, range))
         return false;
      sum += range;
      if(!MathIsValidNumber(sum))
         return false;
   }
   return SimpleAtrFromSum(sum, M5_ATR_PERIOD, atr);
}

// False only while bar/indicator data are not ready; then this same just-opened M5 bar may retry.
bool EvaluateClosedBar(const datetime current_bar_open)
{
   if(!M15WarmupReady(Bars(_Symbol, PERIOD_M15), BarsCalculated(m15_ema20_handle),
                      BarsCalculated(m15_ema50_handle)))
      return false;
   MqlRates bars[];
   ArraySetAsSeries(bars, true);
   if(CopyRates(_Symbol, PERIOD_M5, 1, 25, bars) != 25)
      return false;
   const int m5_seconds = PeriodSeconds(PERIOD_M5);
   if(m5_seconds <= 0 || bars[0].time + m5_seconds != current_bar_open ||
      !PreviousWindowSelected(25, 0, 1, 24, 24))
   {
      Print("Signal skipped: exactly 25 closed M5 bars with a 24-bar preceding window are required.");
      return true;
   }
   for(int i = 0; i < 25; ++i)
   {
      if(!ValidOhlc(bars[i].open, bars[i].high, bars[i].low, bars[i].close))
      {
         Print("Signal skipped: copied M5 history has invalid OHLC geometry.");
         return true;
      }
      if(i > 0 && bars[i].time + m5_seconds != bars[i - 1].time)
      {
         Print("Signal skipped: signal and 24 preceding M5 bars must be contiguous.");
         return true;
      }
   }

   if(!ValidHighLow(bars[1].high, bars[1].low))
      return true;
   double previous_low = bars[1].low;
   double previous_high = bars[1].high;
   // bars[0] is the signal; boundaries intentionally begin at bars[1] and exclude it.
   for(int i = 2; i <= 24; ++i)
      if(!AccumulateSweepBoundaries(bars[i].high, bars[i].low, previous_low, previous_high))
         return true;

   double atr = 0.0;
   double m15_ema20 = 0.0;
   double m15_ema50_1 = 0.0;
   double m15_ema50_4 = 0.0;
   // Fourteen true ranges end at the signal; M15 uses completed shifts 1 and 4.
   if(!ReadM5Atr14(bars, atr) ||
      !ReadCompletedValue(m15_ema20_handle, 20, 1, m15_ema20) ||
      !ReadCompletedValue(m15_ema50_handle, 50, 1, m15_ema50_1) ||
      !ReadCompletedValue(m15_ema50_handle, 50, 4, m15_ema50_4))
      return false;

   bool buy = false;
   if(!SweepReclaimSignal(bars[0].open, bars[0].high, bars[0].low, bars[0].close,
                          previous_low, previous_high, buy))
      return true;
   const bool m15_trend = buy ? (m15_ema20 > m15_ema50_1 && m15_ema50_1 > m15_ema50_4)
                               : (m15_ema20 < m15_ema50_1 && m15_ema50_1 < m15_ema50_4);
   if(!m15_trend)
      return true;

   SubmitSignal(buy, bars[0], atr);
   return true;
}

int OnInit()
{
   if(!IsXauUsdSymbol() || _Period != PERIOD_M5)
   {
      Print("Use an XAUUSD M5 chart with XAU/USD symbol metadata (broker suffixes supported).");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(!IsUsdAccount())
   {
      Print("This fallback requires a USD-denominated account so the USD budget remains meaningful.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(!HasRequiredContractSize())
   {
      Print("This fallback requires SYMBOL_TRADE_CONTRACT_SIZE exactly 100 oz per lot.");
      return INIT_PARAMETERS_INCORRECT;
   }
   const long account_mode = AccountInfoInteger(ACCOUNT_TRADE_MODE);
   const bool real_account = account_mode == ACCOUNT_TRADE_MODE_REAL;
   const bool demo_account = account_mode == ACCOUNT_TRADE_MODE_DEMO;
   const bool tester = MQLInfoInteger(MQL_TESTER) != 0;
   if(!AccountModeAllowed(demo_account, real_account, InpAllowLiveTrading, tester))
   {
      Print("Demo/tester only by default; real requires explicit opt-in. Contest/unknown modes are rejected. This fallback failed its research gates.");
      return INIT_FAILED;
   }
   if(!PositiveFinite(InpFixedLots) || !PositiveFinite(InpRewardRisk) ||
      !ValidUtcOffsetMinutes(InpBrokerUtcOffsetMinutes) ||
      !ValidUtcSessionHours(InpSessionStartUtcHour, InpSessionEndUtcHour) ||
      InpMaxHoldMinutes <= 0 || InpMaxSignalDelaySeconds < 0 ||
      InpMaxSignalDelaySeconds > MAX_SIGNAL_DELAY_SECONDS || InpDeviationPoints == 0 ||
      InpMagic == 0 || InpMagic > (ulong)LONG_MAX)
   {
      Print("Invalid inputs: fixed lots/RR must be positive; UTC session and timing must be valid.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(MathAbs(InpFixedLots - LOCKED_FIXED_LOTS) > 1e-10 ||
      MathAbs(InpRewardRisk - LOCKED_REWARD_RISK) > 1e-10)
   {
      Print("This locked fallback requires exactly 0.01 fixed lots and RR 1.00.");
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
      !PositiveFinite(SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE)))
   {
      Print("Broker must support Bid candles, market orders, and attached SL/TP.");
      return INIT_FAILED;
   }

   m15_ema20_handle = iMA(_Symbol, PERIOD_M15, M15_FAST_EMA_PERIOD, 0, MODE_EMA, PRICE_CLOSE);
   m15_ema50_handle = iMA(_Symbol, PERIOD_M15, M15_SLOW_EMA_PERIOD, 0, MODE_EMA, PRICE_CLOSE);
   if(m15_ema20_handle == INVALID_HANDLE || m15_ema50_handle == INVALID_HANDLE)
   {
      Print("Unable to create completed M15 EMA20/EMA50 handles.");
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
   if(InpSessionStartUtcHour != 7 || InpSessionEndUtcHour != 18 ||
      InpMaxHoldMinutes != 45 || InpMaxSignalDelaySeconds != 30)
      Print("Inputs differ from the locked study defaults; this configuration was not researched.");
   Print("SweepReclaimXAU is an unvalidated failed-development-gate fallback. Waiting for the next closed M5 candle.");
   // Do not evaluate an already-forming/previous signal after attach or restart.
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
   AlignTakeProfit();

   const datetime current_bar_open = iTime(_Symbol, PERIOD_M5, 0);
   if(current_bar_open <= 0)
      return;
   if(last_processed_bar == 0)
   {
      // If history was unavailable on attach, wait for another completed candle.
      last_processed_bar = current_bar_open;
      return;
   }
   if(current_bar_open == last_processed_bar)
      return;
   if(!SignalWindowOpen((long)current_bar_open, (long)TimeCurrent(), InpMaxSignalDelaySeconds))
   {
      last_processed_bar = current_bar_open;
      return;
   }
   if(EvaluateClosedBar(current_bar_open))
      last_processed_bar = current_bar_open;
}
#endif
