// Client-side helpers to mirror/illustrate backend financial logic for display.

export interface EmiRow {
  month: number
  payment: number
  interest: number
  principal: number
  balance: number
}

export function emi(loan: number, annualRatePct: number, months: number): number {
  if (loan <= 0) return 0
  const r = annualRatePct / 100 / 12
  if (r === 0) return loan / months
  return (loan * r * Math.pow(1 + r, months)) / (Math.pow(1 + r, months) - 1)
}

export function schedule(loan: number, annualRatePct: number, months: number, moratoriumMonths = 0): EmiRow[] {
  const r = annualRatePct / 100 / 12
  const rows: EmiRow[] = []
  // Deferred interest: no payment during moratorium, interest capitalises (mirrors backend deferred_interest)
  const capitalised = r === 0 ? 0 : loan * (Math.pow(1 + r, moratoriumMonths) - 1)
  const capitalisedBalance = loan + capitalised
  const remainingMonths = Math.max(months - moratoriumMonths, 1)
  const emiAfter = (() => {
    const bal = capitalisedBalance
    if (r === 0) return bal / remainingMonths
    const factor = Math.pow(1 + r, remainingMonths)
    return (bal * r * factor) / (factor - 1)
  })()
  let running = capitalisedBalance
  for (let i = 1; i <= months; i++) {
    if (i <= moratoriumMonths) {
      // No EMI during moratorium — nothing due
      rows.push({ month: i, payment: 0, interest: 0, principal: 0, balance: Math.round(running * 100) / 100 })
      continue
    }
    const interest = running * r
    let payment = emiAfter
    let principal = Math.min(payment - interest, running)
    running = Math.max(0, running - principal)
    rows.push({
      month: i,
      payment: Math.round(payment * 100) / 100,
      interest: Math.round(interest * 100) / 100,
      principal: Math.round(principal * 100) / 100,
      balance: Math.max(0, Math.round(running * 100) / 100),
    })
  }
  return rows
}
