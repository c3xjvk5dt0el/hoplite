#ifndef MOMENTUM_XAU_CORE_MQH
#define MOMENTUM_XAU_CORE_MQH

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

double RiskVolume(const double budget, const double loss_per_lot,
                  const double min_lot, const double max_lot,
                  const double step)
{
   if(!MathIsValidNumber(budget) || !MathIsValidNumber(loss_per_lot) ||
      !MathIsValidNumber(min_lot) || !MathIsValidNumber(max_lot) || !MathIsValidNumber(step))
      return 0.0;
   if(budget <= 0.0 || loss_per_lot <= 0.0 || min_lot <= 0.0 ||
      max_lot < min_lot || step <= 0.0)
      return 0.0;

   const double cap = MathMin(budget / loss_per_lot, max_lot);
   double volume = MathFloor(cap / step + 1e-9) * step;
   if(volume * loss_per_lot > budget + 1e-8)
      volume -= step;
   if(volume < min_lot - 1e-9)
      return 0.0;
   return NormalizeDouble(volume, 8);
}

#endif
