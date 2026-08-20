"use client";

import { CabecalhoPagina } from "@/components/layout/pagina";
import { StatusDadoBadge } from "@/components/dominio/indicadores";
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
import { percentual } from "@/lib/formato";
import type { Material } from "@/lib/tipos";

export default function PaginaMateriais() {
  const { dados, erro, carregando } = useLista<Material>("/materiais?limite=100");
  const materiais = dados ?? [];

  if (erro) {
    return (
      <>
        <CabecalhoPagina titulo="Materiais" />
        <ErroDeCarregamento erro={erro} />
      </>
    );
  }

  return (
    <>
      <CabecalhoPagina
        titulo="Materiais"
        descricao="Rendimento-padrão, perdas normais e faixas de qualidade alimentam o custo-padrão e o balanço de massa do lote."
      />

      <Cartao className={carregando ? "opacity-60" : undefined}>
        {materiais.length === 0 && !carregando ? (
          <Vazio
            titulo="Nenhum material cadastrado"
            descricao="Cadastre os materiais de entrada e os produtos de saída para começar a apurar lotes."
          />
        ) : (
          <Tabela>
            <thead>
              <tr>
                <Th>Código</Th>
                <Th>Descrição</Th>
                <Th>Família</Th>
                <Th>Tipo</Th>
                <Th>NCM</Th>
                <Th numerica>Rendimento</Th>
                <Th numerica>Perda normal</Th>
                <Th>Status do dado</Th>
              </tr>
            </thead>
            <tbody>
              {materiais.map((material) => (
                <LinhaTabela key={material.id}>
                  <Td className="font-mono text-xs">{material.codigo}</Td>
                  <Td className="font-medium">{material.descricao}</Td>
                  <Td className="text-texto-suave">{material.familia}</Td>
                  <Td>
                    <Distintivo tom={material.tipo === "ENTRADA" ? "info" : "marca"}>
                      {material.tipo === "ENTRADA" ? "Entrada" : "Saída"}
                    </Distintivo>
                  </Td>
                  <Td className="font-mono text-xs text-texto-suave">
                    {material.ncm ?? "—"}
                  </Td>
                  <Td numerica>
                    {material.rendimento_padrao
                      ? percentual(material.rendimento_padrao)
                      : "—"}
                  </Td>
                  <Td numerica>
                    {material.perda_normal_padrao
                      ? percentual(material.perda_normal_padrao)
                      : "—"}
                  </Td>
                  <Td>
                    <StatusDadoBadge status={material.status_dado} />
                  </Td>
                </LinhaTabela>
              ))}
            </tbody>
          </Tabela>
        )}
      </Cartao>

      <p className="mt-3 text-xs text-texto-tenue">
        Material sem NCM não impede o cadastro, mas bloqueia a cotação definitiva:
        a validação é do motor fiscal, não do formulário.
      </p>
    </>
  );
}
