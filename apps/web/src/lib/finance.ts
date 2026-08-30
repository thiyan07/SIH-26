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
  let balance = loan
  for (let i = 1; i <= months; i++) {
    const interest = balance * r
    let principal: number
    let payment: number
    if (i <= moratoriumMonths) {
      payment = 0
      principal = 0
      balance += interest
      rows.push({ month: i, payment, interest, principal, balance: Math.round(balance * 100) / 100 })
      continue
    }
    payment = emi(loan, annualRatePct, months)
    principal = payment - interest
    balance -= principal
    rows.push({
      month: i,
      payment: Math.round(payment * 100) / 100,
      interest: Math.round(interest * 100) / 100,
      principal: Math.round(principal * 100) / 100,
      balance: Math.max(0, Math.round(balance * 100) / 100),
    })
  }
  return rows
}
