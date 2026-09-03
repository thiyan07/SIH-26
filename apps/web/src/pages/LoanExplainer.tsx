import { useAnalysis } from '../lib/analysisStore'
import { Card, CardHeader } from '../components/ui'
import { tr, interpolate } from '../lib/i18n'
import { formatINR } from './Dashboard'

function monthName(n: number | undefined | null, lang: Parameters<typeof tr>[1]): string {
  if (n == null) return '—'
  const names = tr('monthNames', lang).split(',')
  return names[(n - 1 + names.length) % names.length] ?? '—'
}

interface Row {
  month: number
  payment: number
  interest: number
  principal: number
  balance: number
}

interface Term {
  en: string
  ta: string
  hi: string
}

export function LoanExplainer() {
  const { result, lang } = useAnalysis()
  const le = result?.loan_explainer

  if (!result || !le) return null

  const project_cost = le.funding_summary.project_cost
  const own_capital = le.funding_summary.own_capital
  const required_financing = le.funding_summary.required_financing
  const no_loan_required = le.funding_summary.no_loan_required
  const shortfall = le.funding_summary.shortfall
  const shortfall_reason = le.funding_summary.shortfall_reason

  const loan_amount = le.loan_summary.loan_amount
  const interest_rate = le.loan_summary.interest_rate
  const tenure_years = le.loan_summary.tenure_years
  const tenure_months = le.loan_summary.tenure_months
  const moratorium_months = le.loan_summary.moratorium_months
  const scheme_name = le.loan_summary.scheme_name
  const max_loan_allowed = le.loan_summary.max_loan_allowed
  const payment_amount = le.loan_summary.payment_amount
  const total_interest = le.loan_summary.total_interest
  const total_repayment = le.loan_summary.total_repayment
  const number_of_payments = le.loan_summary.number_of_payments

  const repayment_schedule = le.repayment_schedule
  const affordability = le.affordability
  const safety = le.safety
  const terminology = le.terminology
  const data_status = le.data_status

  const operating_profit = affordability.monthly_operating_profit
  const cash_surplus = affordability.cash_surplus_after_payment

  return (
    <div className="space-y-6">
      {/* Funding section */}
      {no_loan_required ? (
        <Card>
          <CardHeader title={tr('noLoanRequired', lang)} />
          <p>{interpolate(tr('sufficientCapital', lang), { capital: `₹${formatINR(own_capital)}`, cost: `₹${formatINR(project_cost)}` })}</p>
        </Card>
      ) : (
        <Card>
          <CardHeader title={tr('yourBusinessFunding', lang)} subtitle={tr('fundingSub', lang)} />
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <p className="text-[11px] text-gray-500">{tr('businessNeed', lang)}</p>
              <p className="text-base font-bold text-gray-900">₹{formatINR(project_cost)}</p>
            </div>
            <div>
              <p className="text-[11px] text-gray-500">{tr('yourMoney', lang)}</p>
              <p className="text-base font-bold text-gray-900">₹{formatINR(own_capital)}</p>
            </div>
            {required_financing > 0 && (
              <div>
                <p className="text-[11px] text-gray-500">{tr('amountToBorrow', lang)}</p>
                <p className="text-base font-bold text-gray-900">₹{formatINR(required_financing)}</p>
              </div>
            )}
            {shortfall > 0 && (
              <div className="rounded-lg bg-amber-50 p-3">
                <p className="text-xs text-amber-800">{tr('shortfall', lang)}: ₹{formatINR(shortfall)} {shortfall_reason || ''}</p>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Loan summary */}
      <Card>
        <CardHeader title={tr('yourLoan', lang)} subtitle={tr('loanSub', lang)} />
        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <p className="text-[11px] text-gray-500">{tr('loanAmount', lang)}</p>
            <p className="text-base font-bold text-gray-900">₹{formatINR(loan_amount)}</p>
          </div>
          {interest_rate !== undefined && interest_rate !== null && (
            <div>
              <p className="text-[11px] text-gray-500">{tr('interestRate', lang)}</p>
              <p className="text-base font-bold text-gray-900">{interest_rate}% {tr('perAnnum', lang)}</p>
            </div>
          )}
          <div>
            <p className="text-[11px] text-gray-500">{tr('tenure', lang)}</p>
            <p className="text-base font-bold text-gray-900">{tenure_years} {tr('years', lang)} ({tenure_months} {tr('months', lang)})</p>
          </div>
          {moratorium_months > 0 && (
            <div>
              <p className="text-[11px] text-gray-500">{tr('moratorium', lang)}</p>
              <p className="text-base font-bold text-gray-900">{moratorium_months} {tr('months', lang)} {tr('interestOnlyDuringMoratorium', lang)}</p>
            </div>
          )}
          {payment_amount !== undefined && payment_amount !== null && (
            <div>
              <p className="text-[11px] text-gray-500">{tr('monthlyPayment', lang)}</p>
              <p className="text-base font-bold text-gray-900">₹{formatINR(payment_amount)} {tr('perMonth', lang)}</p>
            </div>
          )}
          {max_loan_allowed !== undefined && max_loan_allowed !== null && (
            <div>
              <p className="text-[11px] text-gray-500">{tr('maxLoanAllowed', lang)}</p>
              <p className="text-base font-bold text-gray-900">₹{formatINR(max_loan_allowed)}</p>
            </div>
          )}
          {scheme_name && (
            <div>
              <p className="text-[11px] text-gray-500">{tr('scheme', lang)}</p>
              <p className="text-base font-bold text-gray-900">{scheme_name}</p>
            </div>
          )}
        </div>
      </Card>

      {/* Repayment journey */}
      <Card>
        <CardHeader title={tr('repaymentJourney', lang)} subtitle={tr('repaymentJourneySub', lang)} />
        <div className="grid gap-2">
          <div className="rounded-lg bg-gray-50 p-2 text-center text-sm">
            <p className="text-[10px] text-gray-500">{tr('businessNeed', lang)}</p>
            <p>{loan_amount > 0 ? tr('amountToBorrow', lang) : tr('noLoanRequired', lang)}</p>
          </div>
          <div className="rounded-lg bg-gray-50 p-2 text-center text-sm">
            {loan_amount > 0 ? (
              <p>{tr('firstPayment', lang)}: {interpolate(tr('onDate', lang), { date: monthName(repayment_schedule.first_regular_month, lang) })}</p>
            ) : (
              <p>{tr('firstPaymentUnavailable', lang)}</p>
            )}
          </div>
          <div className="rounded-lg bg-gray-50 p-2 text-center text-sm">
            <p>{tr('monthlyPayments', lang)}: {number_of_payments} {tr('payments', lang)}</p>
          </div>
          {loan_amount > 0 && repayment_schedule.last_payment_month && (
            <div className="rounded-lg bg-gray-50 p-2 text-center text-sm">
              <p>{tr('finalPayment', lang)}: {interpolate(tr('onDateFinal', lang), { date: monthName(repayment_schedule.last_payment_month, lang) })}</p>
            </div>
          )}
        </div>
      </Card>

      {/* Repayment table */}
      <Card>
        <CardHeader title={tr('repaymentSchedule', lang)} subtitle={tr('scheduleSub', lang)} />
        <div className="space-y-2">
          <p className="text-xs text-gray-500">{interpolate(tr('showingFirst12', lang), { total: repayment_schedule.rows.length })}</p>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-gray-500">
                <th className="py-2 pr-4">{tr('month', lang)}</th>
                <th className="py-2 pr-4">{tr('payment', lang)}</th>
                <th className="py-2 pr-4">{tr('interest', lang)}</th>
                <th className="py-2 pr-4">{tr('principal', lang)}</th>
                <th className="py-2">{tr('balance', lang)}</th>
              </tr>
            </thead>
            <tbody>
              {repayment_schedule.rows.slice(0, 12).map((r: Row) => (
                <tr key={r.month} className="border-b border-gray-50">
                  <td className="py-1.5 pr-4 text-gray-500">{r.month}</td>
                  <td className="py-1.5 pr-4">{r.payment > 0 ? `₹${formatINR(r.payment)}` : '—'}</td>
                  <td className="py-1.5 pr-4">₹{formatINR(r.interest)}</td>
                  <td className="py-1.5 pr-4">₹{formatINR(r.principal)}</td>
                  <td className="py-1.5">₹{formatINR(r.balance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {repayment_schedule.rows.length > 12 && (
            <p className="mt-2 text-xs text-gray-400">{interpolate(tr('showingFirst12', lang), { total: repayment_schedule.rows.length })}</p>
          )}
        </div>
      </Card>

      {/* Affordability */}
      <Card>
        <CardHeader title={tr('canYourBusinessAffordIt', lang)} subtitle={tr('affordabilitySub', lang)} />
        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <p className="text-[11px] text-gray-500">{tr('monthlyOperatingProfit', lang)}</p>
            <p className="text-base font-bold text-gray-900">₹{formatINR(operating_profit)}</p>
          </div>
          <div>
            <p className="text-[11px] text-gray-500">{tr('monthlyLoanPayment', lang)}</p>
            <p className="text-base font-bold text-gray-900">₹{formatINR(payment_amount)}</p>
          </div>
          {payment_amount > 0 && (
            <div>
              <p className="text-[11px] text-gray-500">{tr('surplusAfterPayment', lang)}</p>
              <p className="text-base font-bold text-gray-900">₹{formatINR(cash_surplus)}</p>
            </div>
          )}
          {safety && (
            <div className="rounded-lg p-3 mt-3">
              <p className="text-xs font-medium">{tr(safety.level, lang)}</p>
              <p>{interpolate(tr('safetyDetail', lang), { businessSurplus: `₹${formatINR(safety.business_surplus)}`, loanPayment: `₹${formatINR(safety.loan_payment)}`, gap: `₹${formatINR(safety.gap)}` })}</p>
            </div>
          )}
        </div>
      </Card>

      {/* Terminology */}
      <Card>
        <CardHeader title={tr('keyTerms', lang)} subtitle={tr('keyTermsSub', lang)} />
        <div className="grid gap-2">
          {Object.entries(terminology).map(([term, value]) => {
            const t = value as Term
            const label = lang === 'ta' ? t.ta : lang === 'hi' ? t.hi : t.en
            return (
              <div key={term} className="rounded-lg bg-gray-50 p-2 text-xs">
                <p className="font-medium text-gray-700">{label}</p>
                <p className="text-gray-500">EN · {t.en}</p>
                <p className="text-gray-500">TA · {t.ta}</p>
                <p className="text-gray-500">HI · {t.hi}</p>
              </div>
            )
          })}
        </div>
      </Card>

      {/* FAQ */}
      <Card>
        <CardHeader title={tr('howIsMyPaymentCalculated', lang)} subtitle={tr('faqSub', lang)} />
        <details>
          <summary>{tr('expandToSee', lang)}</summary>
          <p>{tr('paymentCalculationExplanation', lang)}</p>
          {loan_amount > 0 && (
            <p>{interpolate(tr('paymentCalcBreakdown', lang), {
              loan: `₹${formatINR(loan_amount)}`,
              rate: interest_rate != null ? `${interest_rate}%` : '—',
              years: tenure_years != null ? `${tenure_years} ${tr('years', lang)}` : '—',
              emi: `₹${formatINR(payment_amount)}`,
            })}</p>
          )}
          {total_interest !== undefined && total_interest !== null && (
            <p>{tr('totalInterestNote', lang)}: ₹{formatINR(total_interest)}</p>
          )}
          {data_status.no_loan || loan_amount <= 0 && (
            <p>{tr('noLoanCalculationNeeded', lang)}</p>
          )}
        </details>
      </Card>

      {/* Total cost */}
      <Card>
        <CardHeader title={tr('totalCost', lang)} subtitle={tr('totalCostSub', lang)} />
        {loan_amount > 0 && (
          <div>
            <p>{tr('borrowed', lang)}: ₹{formatINR(loan_amount)}</p>
            {total_interest !== undefined && total_interest !== null && (
              <p>{tr('interest', lang)}: ₹{formatINR(total_interest)}</p>
            )}
            {total_repayment !== undefined && total_repayment !== null && (
              <p>{tr('totalRepayment', lang)}: ₹{formatINR(total_repayment)}</p>
            )}
          </div>
        )}
        {no_loan_required && (
          <p>{tr('noLoanTotal', lang)}: {tr('fullyCoveredByOwn', lang)}</p>
        )}
      </Card>
    </div>
  )
}