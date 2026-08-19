import { CabecalhoPagina } from "@/components/layout/pagina";
import { Alerta, StatusFiscalBadge } from "@/components/dominio/indicadores";
import { ErroDeCarregamento } from "@/components/ui/estado-api";
import {
  Cartao,
  Distintivo,
  LinhaTabela,
  Tabela,
  Td,
  Th,
  Vazio,
} from "@/components/ui/primitivos";
import { api } from "@/lib/api";
import { percentual, rotulo, vigencia } from "@/lib/formato";
import type { RegraTributaria } from "@/lib/tipos";

export const dynamic = "force-dynamic";

/** Efeito economico da regra, em uma palavra. */
function EfeitoDaRegra({ regra }: { regra: RegraTributaria }) {
  if (regra.compoe_deducao_venda) {
    return <Distintivo tom="atencao">Deduz do preço (r)</Distintivo>;
  }
  if (regra.gera_credito_compra) {
    return <Distintivo tom="ok">Credita na compra</Distintivo>;
  }
  if (regra.incide_sobre_lucro) {
    return <Distintivo tom="info">Incide sobre o lucro</Distintivo>;
  }
  return <Distintivo tom="neutro">Sem efeito em r</Distintivo>;
}

export default async function PaginaRegras() {
  let regras: RegraTributaria[] = [];
  let erro: unknown = null;

  try {
    const pagina = await api.lista<RegraTributaria>("/tributario/regras?limite=100");
    regras = pagina.itens;
  } catch (e) {
    erro = e;
  }

  if (erro) {
    return (
      <>
        <CabecalhoPagina titulo="Matriz de regras tributárias" />
        <ErroDeCarregamento erro={erro} />
      </>
    );
  }

  const provisorias = regras.filter((r) => r.status === "PROVISORIA").length;
  const condicionais = regras.filter((r) => r.requer_confirmacao_condicao).length;

  return (
    <>
      <CabecalhoPagina
        titulo="Matriz de regras tributárias"
        descricao="O módulo tributário é uma matriz de regras versionadas por vigência, não um percentual único. A regra é escolhida pela data da operação, nunca pela data de hoje."
      />

      {provisorias > 0 ? (
        <Alerta
          severidade="atencao"
          titulo={`${provisorias} de ${regras.length} regras ainda provisórias`}
          className="mb-6"
        >
          Enquanto o responsável fiscal não validar cada regra, nenhuma cotação
          pode ser classificada como definitiva — mesmo com todos os demais
          campos preenchidos.
        </Alerta>
      ) : null}

      <Cartao>
        {regras.length === 0 ? (
          <Vazio titulo="Nenhuma regra cadastrada" />
        ) : (
          <Tabela>
            <thead>
              <tr>
                <Th>Código</Th>
                <Th>Tributo</Th>
                <Th>Operação</Th>
                <Th>Regime</Th>
                <Th numerica>Alíquota</Th>
                <Th>Efeito</Th>
                <Th>Vigência</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {regras.map((regra) => (
                <LinhaTabela key={regra.id}>
                  <Td className="font-mono text-xs">{regra.codigo}</Td>
                  <Td className="font-medium">{regra.tributo}</Td>
                  <Td className="text-texto-suave">{rotulo(regra.tipo_operacao)}</Td>
                  <Td className="text-texto-suave">
                    {regra.regime_tributario ? rotulo(regra.regime_tributario) : "Todos"}
                  </Td>
                  <Td numerica>
                    {regra.percentual_presuncao_base && regra.aliquota
                      ? `${percentual(regra.percentual_presuncao_base, 0)} × ${percentual(regra.aliquota, 0)}`
                      : regra.aliquota
                        ? percentual(regra.aliquota)
                        : "por faixa"}
                  </Td>
                  <Td>
                    <EfeitoDaRegra regra={regra} />
                  </Td>
                  <Td className="text-xs text-texto-suave">
                    {vigencia(regra.vigencia_inicio, regra.vigencia_fim)}
                  </Td>
                  <Td>
                    <StatusFiscalBadge status={regra.status} />
                  </Td>
                </LinhaTabela>
              ))}
            </tbody>
          </Tabela>
        )}
      </Cartao>

      {condicionais > 0 ? (
        <p className="mt-3 text-xs text-texto-tenue">
          {condicionais} regra(s) são condicionais — como o crédito da Lei
          15.394/2026, que só reduz o custo depois de confirmado que o material é
          usado como matéria-prima por pessoa jurídica no lucro real.
        </p>
      ) : null}
    </>
  );
}
