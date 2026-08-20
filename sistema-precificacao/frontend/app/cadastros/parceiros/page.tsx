"use client";

import { CabecalhoPagina } from "@/components/layout/pagina";
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
import { useLista } from "@/lib/dados";
import { percentual, rotulo } from "@/lib/formato";
import type { Parceiro } from "@/lib/tipos";

const TOM_REGIME: Record<string, "ok" | "info" | "atencao" | "neutro"> = {
  LUCRO_REAL: "ok",
  LUCRO_PRESUMIDO: "info",
  SIMPLES_NACIONAL: "atencao",
};

export default function PaginaParceiros() {
  const { dados, erro, carregando } = useLista<Parceiro>("/parceiros?limite=100");
  const parceiros = dados ?? [];

  if (erro) {
    return (
      <>
        <CabecalhoPagina titulo="Parceiros" />
        <ErroDeCarregamento erro={erro} />
      </>
    );
  }

  return (
    <>
      <CabecalhoPagina
        titulo="Parceiros"
        descricao="Fornecedores, clientes e transportadores. O regime tributário e a condição de contribuinte são chave da regra fiscal, não dado cadastral."
      />

      <Cartao className={carregando ? "opacity-60" : undefined}>
        {parceiros.length === 0 && !carregando ? (
          <Vazio titulo="Nenhum parceiro cadastrado" />
        ) : (
          <Tabela>
            <thead>
              <tr>
                <Th>Código</Th>
                <Th>Nome</Th>
                <Th>Papel</Th>
                <Th>Regime</Th>
                <Th>Contribuinte ICMS</Th>
                <Th>UF</Th>
                <Th numerica>Prazo</Th>
                <Th numerica>Inadimplência</Th>
              </tr>
            </thead>
            <tbody>
              {parceiros.map((parceiro) => {
                const prazo =
                  parceiro.prazo_recebimento_dias ?? parceiro.prazo_pagamento_dias;
                return (
                  <LinhaTabela key={parceiro.id}>
                    <Td className="font-mono text-xs">{parceiro.codigo}</Td>
                    <Td className="font-medium">{parceiro.nome}</Td>
                    <Td className="text-texto-suave">{rotulo(parceiro.papel)}</Td>
                    <Td>
                      {parceiro.regime_tributario ? (
                        <Distintivo
                          tom={TOM_REGIME[parceiro.regime_tributario] ?? "neutro"}
                        >
                          {rotulo(parceiro.regime_tributario)}
                        </Distintivo>
                      ) : (
                        <span className="text-texto-tenue">—</span>
                      )}
                    </Td>
                    <Td>
                      {parceiro.contribuinte_icms ? (
                        <Distintivo tom="ok">Sim</Distintivo>
                      ) : (
                        <Distintivo tom="neutro">Não</Distintivo>
                      )}
                    </Td>
                    <Td className="text-texto-suave">{parceiro.uf}</Td>
                    <Td numerica>{prazo != null ? `${prazo} d` : "—"}</Td>
                    <Td numerica>
                      {parceiro.inadimplencia_historica
                        ? percentual(parceiro.inadimplencia_historica)
                        : "—"}
                    </Td>
                  </LinhaTabela>
                );
              })}
            </tbody>
          </Tabela>
        )}
      </Cartao>

      <p className="mt-3 text-xs text-texto-tenue">
        A inadimplência histórica alimenta as provisões de risco do preço
        sustentável — a especificação proíbe percentual genérico de imprevistos.
      </p>
    </>
  );
}
