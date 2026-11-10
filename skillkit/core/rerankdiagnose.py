"""Pure report-only dev diagnostics for the registered M-all rerank grid."""
import itertools
import math

from . import lexmetrics, rungdiagnose as common, rungtune
from .route import rerank, semantic

GRID = dict(mode=['replace', 'fuse'], doc=['card', 'maxint'],
            tau_r_quantiles=[50, 60, 70, 80, 90], delta_r=[0, .05, .10],
            nu=['off', 0], tau_L=[6, 'inf'])
SCOPE = common.SCOPE
ABSTAIN = common.ABSTAIN


def feasible(point, relaxed=()):
    return (point['explicit'] == 0
            and ('T2' in relaxed or point['hard_neg_fp'] is not None and point['hard_neg_fp'] <= .05)
            and ('T3' in relaxed or point['must_not'] == 0)
            and ('T5' in relaxed or point['abstain_recall'] is not None and point['abstain_recall'] >= .75))


def pareto(points, constrained=False):
    """D0 dominance convention, with the registered zero-hit T3 constraint."""
    selected = [i for i, p in enumerate(points) if not constrained or feasible(p)]
    return [selected[i] for i in common.pareto([points[i] for i in selected])]


def kill_rule(top1, score_auc, introduced):
    if top1 is None or score_auc is None:
        raise ValueError('kill rule needs T1 and both AUC label classes')
    flags = dict(no_abstention_t1_below_088=top1 < .88,
                 score_auc_below_080=score_auc < .80, introduced_must_not=introduced > 0)
    return dict(flags, verdict='KILL' if any(flags.values()) else 'CONTINUE',
                no_abstention_t1=top1, score_auc=score_auc,
                introduced_must_not_count=introduced)


def overall_kill(rules):
    if not rules:
        raise ValueError('kill rule needs variants')
    return 'KILL' if all(r['verdict'] == 'KILL' for r in rules) else 'CONTINUE'


class Search:
    """Reuse production ranking and escalation, never invoke a model or write."""
    def __init__(self, cases, records, by_id, lexical_params):
        self.cases, self.records, self.by_id = cases, records, by_id
        self.lexical_params = lexical_params
        self.cache = {}

    def ranked(self, i, mode, doc, nu):
        key = (i, mode, doc, nu)
        if key not in self.cache:
            r = self.records[i]
            self.cache[key] = rerank.rank(r['groups'], r['totals'],
                                         dict(rerank.defaults(), mode=mode, doc=doc, nu=nu))[0]
        return self.cache[key]

    def signals(self, i, mode, doc, nu):
        rows = self.ranked(i, mode, doc, nu)
        p1 = rows[0]['p'] if rows else 0.0
        p2 = rows[1]['p'] if len(rows) > 1 else 0.0
        return p1, p1 - p2

    def escalated(self, i, params):
        r = self.records[i]
        return semantic.should_escalate(r['got'], r['scored'], params)

    def evaluate(self, params):
        out = []
        for i, r in enumerate(self.records):
            rows = self.ranked(i, params['mode'], params['doc'], params['nu'])
            reason, _ = rerank.decision(rows, params)
            out.append(r['got'] if not self.escalated(i, params) else
                       r['primaries'][rows[0]['id']] if reason.startswith('rerank_primary:') else ABSTAIN)
        return out

    def no_abstention(self, mode, doc):
        ranked, gots = [], []
        p = dict(rerank.defaults(), mode=mode, doc=doc)
        for i, r in enumerate(self.records):
            rows = self.ranked(i, mode, doc, 'off')
            if self.escalated(i, p):
                ranked.append([row['id'] for row in rows])
                gots.append(r['primaries'][rows[0]['id']] if rows else ABSTAIN)
            else:
                ranked.append(r['lexical_rank'] if r['got']['primary'] is not None else [])
                gots.append(r['got'])
        return ranked, gots


def must_not_counts(cases, gots, lexical, ids):
    hits = [i for i in ids if lexmetrics.violates(cases[i], gots[i])]
    same = sum(gots[i]['primary'] == lexical[i]['primary'] and
               lexmetrics.violates(cases[i], lexical[i]) for i in hits)
    return dict(hits=len(hits), same_primary_with_rung_off=same, introduced_or_changed=len(hits)-same)


def oracle_report(cases, ids_by_view, ranked):
    report = {}
    for name, ids in ids_by_view.items():
        parts = dict(all=ids, routed=[i for i in ids if not cases[i]['expect'].get('abstain')],
                     abstained=[i for i in ids if cases[i]['expect'].get('abstain')])
        report[name] = {}
        for part, chosen in parts.items():
            def primary(i):
                return None if cases[i]['expect'].get('abstain') else (ranked[i][0] if ranked[i] else None)
            t1 = [i for i in chosen if cases[i]['kind'] in ('positive', 'neighbour')]
            correct = sum(primary(i) == cases[i]['expect'].get('primary') for i in chosen)
            report[name][part] = dict(n=len(chosen), primary_correct=correct,
                primary_accuracy=common.ratio(correct, len(chosen)), t1_n=len(t1),
                top1=common.ratio(sum(primary(i) == cases[i]['expect'].get('primary') for i in t1), len(t1)))
    return report


def separability(search, ids_by_view, mode, doc):
    out = {}
    for name, ids in ids_by_view.items():
        labels = [not search.cases[i]['expect'].get('abstain', False) for i in ids]
        signals = [search.signals(i, mode, doc, 'off') for i in ids]
        out[name] = dict(n=len(ids), route_labels=sum(labels), abstain_labels=len(ids)-sum(labels),
            score_auc=common.auc([p for p, m in signals], labels),
            margin_auc=common.auc([m for p, m in signals], labels),
            margin_quantiles=common.quantiles([m for p, m in signals]))
    return out


class Counts(common.Counts):
    """Exact D0 bitsets plus explicit numerators, denominators and precision."""
    def metrics(self, routed, name):
        out = super().metrics(routed, name)
        m = self.masks[name]
        routed_n = (routed & m['view']).bit_count()
        predicted_abstain = m['n'] - routed_n
        true_abstain = (~routed & m['want_abstain']).bit_count()
        out.update(routed_n=routed_n, abstained_n=predicted_abstain,
            top1_count=(((routed & m['correct_route']) | (~routed & m['correct_abstain'])) & m['t1']).bit_count(),
            hard_neg_fp_count=(routed & m['wrong_negative']).bit_count(),
            abstain_true_count=true_abstain,
            abstain_precision=common.ratio(true_abstain, predicted_abstain))
        return out

    def __init__(self, cases, gots, by_id, ids_by_view):
        super().__init__(cases, gots, by_id, ids_by_view)
        for name, ids in ids_by_view.items():
            self.masks[name]['view'] = sum(1 << i for i in ids)


def frontier(search, ids_by_view):
    metrics = ('top1', 'top1_count', 'hard_neg_fp', 'hard_neg_fp_count', 'must_not',
               'explicit', 'abstain_recall', 'abstain_precision', 'abstain_true_count',
               'routed_n', 'abstained_n')
    columns = ['mode', 'doc', 'quantile', 'tau_r', 'delta_r', 'nu', 'tau_L']
    columns += [name + '.' + metric for name in ids_by_view for metric in metrics]
    columns += ['introduced_must_not_all', 'introduced_must_not_reachable']
    rows, points = [], []
    lexical = [r['got'] for r in search.records]
    for mode, doc in itertools.product(GRID['mode'], GRID['doc']):
        for q, delta, nu, tau_L in itertools.product(GRID['tau_r_quantiles'], GRID['delta_r'], GRID['nu'], GRID['tau_L']):
            p = dict(rerank.defaults(), mode=mode, doc=doc, nu=nu, delta_r=delta,
                     tau_L=math.inf if tau_L == 'inf' else tau_L)
            escalated = [search.escalated(i, p) for i in range(len(search.cases))]
            values = [search.signals(i, mode, doc, 'off')[0] for i in ids_by_view['reachable'] if escalated[i]]
            p['tau_r'] = rungtune.quantile(values, q)
            gots = search.evaluate(p)
            routed = sum(1 << i for i, g in enumerate(gots) if g['primary'] is not None)
            counts = Counts(search.cases, gots, search.by_id, ids_by_view)
            estimates = {name: counts.metrics(routed, name) for name in ids_by_view}
            points.append(dict(estimates['reachable'], explicit=estimates['all']['explicit']))
            rows.append([mode, doc, q, p['tau_r'], delta, nu, tau_L] +
                [estimates[name][metric] for name in ids_by_view for metric in metrics] +
                [must_not_counts(search.cases, gots, lexical, ids_by_view[name])['introduced_or_changed']
                 for name in ('all', 'reachable')])

    def best(relaxed=(), config=None):
        ids = [i for i, point in enumerate(points) if feasible(point, relaxed)
               and (config is None or rows[i][:2] == list(config))]
        # Same deterministic objective as D0: maximum T1, then first grid row.
        return max(ids, key=lambda i: (points[i]['top1'] if points[i]['top1'] is not None else -1, -i)) if ids else None
    relaxed = ('T2', 'T3', 'T5')
    return dict(columns=columns, points=rows, n_points=len(rows),
        best_constrained=best(), best_unconstrained=best(relaxed),
        best_relax_one={name: best((name,)) for name in relaxed},
        best_by_mode_doc={mode + '/' + doc: dict(constrained=best(config=(mode, doc)),
            unconstrained=best(relaxed, (mode, doc))) for mode, doc in itertools.product(GRID['mode'], GRID['doc'])},
        pareto_constrained=pareto(points, True), pareto_unconstrained=pareto(points))


def diagnose(search):
    ids = common.view_ids(search.cases, search.by_id)
    lexical = [r['got'] for r in search.records]
    ranking, oracle, gates, bans = {}, {}, {}, {}
    for mode, doc in itertools.product(GRID['mode'], GRID['doc']):
        key = mode + '/' + doc
        ranked, gots = search.no_abstention(mode, doc)
        margins = [search.signals(i, mode, doc, 'off')[1] for i in range(len(search.cases))]
        ranking[key] = common.ranking_report(search.cases, ids, ranked, margins)
        oracle[key] = oracle_report(search.cases, ids, ranked)
        gates[key] = separability(search, ids, mode, doc)
        bans[key] = {name: must_not_counts(search.cases, gots, lexical, chosen) for name, chosen in ids.items()}
    front = frontier(search, ids)
    best_t1 = max((r['reachable']['top1'] for r in ranking.values() if r['reachable']['top1'] is not None), default=None)
    best_auc = max((g['all']['score_auc'] for g in gates.values() if g['all']['score_auc'] is not None), default=None)
    introduced = max([b['all']['introduced_or_changed'] for b in bans.values()] +
                     [row[front['columns'].index('introduced_must_not_all')] for row in front['points']])
    return dict(views={name: dict(n=len(chosen),
        t1_n=sum(search.cases[i]['kind'] in ('positive', 'neighbour') for i in chosen),
        negative_n=sum(search.cases[i]['kind'] == 'negative' for i in chosen),
        expected_abstain_n=sum(bool(search.cases[i]['expect'].get('abstain')) for i in chosen),
        must_not_n=sum(bool(search.cases[i]['expect'].get('must_not')) for i in chosen)) for name, chosen in ids.items()},
        no_abstention=ranking, oracle_gate=oracle, gate_separability=gates,
        must_not_diagnosis=bans, frontier=front, kill=kill_rule(best_t1, best_auc, introduced))
