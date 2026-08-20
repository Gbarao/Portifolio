"""Gera o manual de instalacao e primeiros passos em PDF.

Uso:

    cd sistema-precificacao/backend
    .venv/bin/pip install -e ".[docs]"
    .venv/bin/python ../docs/manual/gerar_manual.py \
        ../docs/manual-instalacao-e-primeiros-passos.pdf

O PDF gerado fica versionado junto: quem so quer ler nao precisa gerar nada.
Regenere sempre que a instalacao ou o fluxo de uso mudarem.
"""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    ListFlowable,
    ListItem,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# --------------------------------------------------------------------- cores
VERDE = colors.HexColor("#14664F")
VERDE_CLARO = colors.HexColor("#E7F2EE")
TINTA = colors.HexColor("#1A1A1F")
TINTA_SUAVE = colors.HexColor("#5A5A63")
TINTA_TENUE = colors.HexColor("#8A8A93")
BORDA = colors.HexColor("#DDDDE2")
CODIGO_FUNDO = colors.HexColor("#F5F5F7")
ATENCAO_FUNDO = colors.HexColor("#FFF6E3")
ATENCAO_BORDA = colors.HexColor("#E8B84B")

LARGURA_UTIL = A4[0] - 4 * cm

# -------------------------------------------------------------------- estilos
base = getSampleStyleSheet()

E = {
    "titulo_capa": ParagraphStyle(
        "titulo_capa", parent=base["Title"], fontName="Helvetica-Bold",
        fontSize=30, leading=36, textColor=VERDE, alignment=TA_LEFT, spaceAfter=6,
    ),
    "sub_capa": ParagraphStyle(
        "sub_capa", parent=base["Normal"], fontName="Helvetica",
        fontSize=13, leading=19, textColor=TINTA_SUAVE, alignment=TA_LEFT,
    ),
    "h1": ParagraphStyle(
        "h1", parent=base["Heading1"], fontName="Helvetica-Bold",
        fontSize=17, leading=22, textColor=VERDE, spaceBefore=20, spaceAfter=8,
    ),
    "h2": ParagraphStyle(
        "h2", parent=base["Heading2"], fontName="Helvetica-Bold",
        fontSize=12.5, leading=17, textColor=TINTA, spaceBefore=14, spaceAfter=5,
    ),
    "p": ParagraphStyle(
        "p", parent=base["Normal"], fontName="Helvetica",
        fontSize=10, leading=15.5, textColor=TINTA, alignment=TA_JUSTIFY,
        spaceAfter=7,
    ),
    "p_pequeno": ParagraphStyle(
        "p_pequeno", parent=base["Normal"], fontName="Helvetica",
        fontSize=8.8, leading=13, textColor=TINTA_SUAVE, spaceAfter=5,
    ),
    "codigo": ParagraphStyle(
        "codigo", parent=base["Code"], fontName="Courier",
        fontSize=8.6, leading=13, textColor=TINTA,
    ),
    "celula": ParagraphStyle(
        "celula", parent=base["Normal"], fontName="Helvetica",
        fontSize=8.8, leading=12.5, textColor=TINTA,
    ),
    "celula_cabecalho": ParagraphStyle(
        "celula_cabecalho", parent=base["Normal"], fontName="Helvetica-Bold",
        fontSize=8.2, leading=11, textColor=colors.white,
    ),
    "item": ParagraphStyle(
        "item", parent=base["Normal"], fontName="Helvetica",
        fontSize=10, leading=15, textColor=TINTA, spaceAfter=3,
    ),
}


def p(texto: str, estilo: str = "p") -> Paragraph:
    return Paragraph(texto, E[estilo])


def codigo(*linhas: str) -> Table:
    """Bloco de comandos, com fundo e recuo."""

    conteudo = "<br/>".join(
        linha.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        for linha in linhas
    )
    tabela = Table(
        [[Paragraph(conteudo, E["codigo"])]], colWidths=[LARGURA_UTIL]
    )
    tabela.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), CODIGO_FUNDO),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDA),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    return tabela


def aviso(titulo: str, texto: str) -> Table:
    """Caixa de atencao."""

    interno = [
        Paragraph(f"<b>{titulo}</b>", ParagraphStyle(
            "aviso_t", parent=E["p"], fontSize=9.5, leading=13,
            textColor=colors.HexColor("#8A6100"), spaceAfter=3,
        )),
        Paragraph(texto, ParagraphStyle(
            "aviso_c", parent=E["p"], fontSize=9.5, leading=14, spaceAfter=0,
        )),
    ]
    tabela = Table([[interno]], colWidths=[LARGURA_UTIL])
    tabela.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), ATENCAO_FUNDO),
            ("LINEBEFORE", (0, 0), (0, -1), 3, ATENCAO_BORDA),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ])
    )
    return tabela


def tabela(cabecalho: list[str], linhas: list[list[str]], larguras: list[float]) -> Table:
    dados = [[Paragraph(c, E["celula_cabecalho"]) for c in cabecalho]]
    dados += [[Paragraph(c, E["celula"]) for c in linha] for linha in linhas]

    t = Table(dados, colWidths=larguras, repeatRows=1)
    t.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), VERDE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDA),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFB")]),
        ])
    )
    return t


def ficha(linhas: list[list[str]], largura_rotulo: float) -> Table:
    """Tabela sem cabecalho, para pares rotulo/valor."""

    dados = [[Paragraph(c, E["celula"]) for c in linha] for linha in linhas]
    t = Table(dados, colWidths=[largura_rotulo, LARGURA_UTIL - largura_rotulo])
    t.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEABOVE", (0, 0), (-1, 0), 1.2, VERDE),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDA),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ])
    )
    return t


def lista(itens: list[str]) -> ListFlowable:
    return ListFlowable(
        [ListItem(p(item, "item"), leftIndent=14) for item in itens],
        bulletType="bullet", bulletFontSize=7, bulletOffsetY=1,
        leftIndent=12, bulletColor=VERDE,
    )


def passo(numero: str, titulo: str) -> Table:
    """Cabecalho de passo numerado."""

    marcador = Table(
        [[Paragraph(numero, ParagraphStyle(
            "num", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=12, leading=15, textColor=colors.white, alignment=1,
        ))]],
        colWidths=[0.85 * cm], rowHeights=[0.85 * cm],
    )
    marcador.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), VERDE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    t = Table(
        [[marcador, Paragraph(titulo, ParagraphStyle(
            "passo_t", parent=E["h1"], spaceBefore=0, spaceAfter=0,
        ))]],
        colWidths=[1.3 * cm, LARGURA_UTIL - 1.3 * cm],
    )
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


# ------------------------------------------------------------------ conteudo
def capa() -> list:
    return [
        Spacer(1, 5 * cm),
        p("Sistema de custeio e precificação", "titulo_capa"),
        p("para operações de reciclagem", "titulo_capa"),
        Spacer(1, 0.6 * cm),
        p(
            "Manual de instalação e primeiros passos<br/>"
            "Como colocar o sistema no ar e começar a usá-lo",
            "sub_capa",
        ),
        Spacer(1, 1.4 * cm),
        ficha(
            [
                ["<b>Versão do sistema</b>", "0.1.0"],
                ["<b>Baseado em</b>", "Modelo de precificação para operações de reciclagem, v1.1"],
                ["<b>Repositório</b>", "github.com/Gbarao/Portifolio"],
                ["<b>Branch</b>", "claude/recycling-costing-pricing-system-hxvl8t"],
                ["<b>Pasta do projeto</b>", "sistema-precificacao/"],
            ],
            5 * cm,
        ),
        Spacer(1, 1 * cm),
        aviso(
            "Leia antes de usar para valer",
            "O sistema já vem com uma matriz tributária de exemplo, mas todas as "
            "regras estão marcadas como <b>provisórias</b>. Enquanto o responsável "
            "fiscal não validar cada uma, o sistema se recusa a classificar qualquer "
            "cotação como definitiva. Isso é proposital, e a seção 7 deste manual "
            "explica como fazer essa validação.",
        ),
    ]


def parte_instalacao() -> list:
    return [
        p("O que este sistema faz", "h1"),
        p(
            "Ele calcula quanto custa cada lote de material reciclável — da compra à "
            "entrega — e transforma esse custo em preço de venda. Não em um preço só: "
            "em <b>cinco</b>, cada um com uma finalidade diferente, do preço de "
            "emergência ao preço-alvo. Para cada número que produz, guarda a memória "
            "de cálculo: fórmula, entradas, fonte e vigência da regra usada."
        ),

        passo("1", "Instale o Python (uma vez só)"),
        p(
            "O sistema precisa de um único programa auxiliar: o <b>Python</b>, versão "
            "3.11 ou mais nova. Se o computador já tiver, pule para o passo 2."
        ),
        tabela(
            ["Sistema", "Como instalar"],
            [
                ["<b>Windows</b>",
                 "Baixe em <font face='Courier'>python.org/downloads</font> e execute o "
                 "instalador. Na primeira tela, marque a caixa "
                 "<b>“Add Python to PATH”</b> antes de clicar em Install — sem ela o "
                 "sistema não encontra o Python depois."],
                ["<b>macOS</b>",
                 "Baixe em <font face='Courier'>python.org/downloads</font> e execute o "
                 "instalador. Nada mais precisa ser marcado."],
                ["<b>Linux</b>",
                 "Normalmente já vem instalado. Se não, use o gerenciador da sua "
                 "distribuição, por exemplo "
                 "<font face='Courier'>sudo apt install python3 python3-venv</font>."],
            ],
            [2.6 * cm, LARGURA_UTIL - 2.6 * cm],
        ),

        passo("2", "Abra a pasta do sistema"),
        p(
            "Descompacte a pasta do sistema em um lugar de sua preferência — a Área "
            "de Trabalho serve. Dentro dela você verá três arquivos com nome "
            "começando em <b>INICIAR</b>, um para cada sistema operacional."
        ),
        aviso(
            "Mantenha a pasta inteira junta",
            "O arquivo INICIAR precisa das outras pastas ao lado dele. Não mova só "
            "esse arquivo para outro lugar — mova a pasta inteira, se precisar.",
        ),

        passo("3", "Clique duas vezes no arquivo INICIAR"),
        p("Escolha o arquivo correspondente ao seu computador:"),
        tabela(
            ["Sistema", "Arquivo"],
            [
                ["<b>Windows</b>", "<font face='Courier'>INICIAR-Windows.bat</font>"],
                ["<b>macOS</b>", "<font face='Courier'>INICIAR-Mac.command</font>"],
                ["<b>Linux</b>", "<font face='Courier'>INICIAR-Linux.sh</font>"],
            ],
            [3.4 * cm, LARGURA_UTIL - 3.4 * cm],
        ),
        Spacer(1, 0.4 * cm),
        p(
            "Uma janela preta de texto vai abrir. É normal — é ela que mostra o "
            "andamento. Na <b>primeira vez</b>, o sistema instala o que precisa; isso "
            "leva alguns minutos e acontece apenas uma vez. Você verá algo assim:"
        ),
        codigo(
            "Verificando o computador",
            "  OK  Python 3.12 encontrado",
            "  OK  Telas encontradas",
            "",
            "Instalando (isso acontece so na primeira vez)",
            "  OK  Ambiente pronto",
            "  OK  Bibliotecas instaladas",
            "  OK  Banco de dados pronto",
        ),

        passo("4", "Responda a única pergunta"),
        p(
            "O instalador pergunta se você quer começar com <b>dados de exemplo</b>: "
            "materiais, parceiros, um lote completo e uma matriz tributária de "
            "demonstração."
        ),
        lista([
            "Se está conhecendo o sistema, responda <b>S</b> (ou apenas tecle Enter). "
            "Com dados dentro, todas as telas ficam compreensíveis.",
            "Se já vai usar para valer, responda <b>n</b> e comece com a base vazia.",
        ]),
        Spacer(1, 0.3 * cm),
        p(
            "Essa pergunta aparece uma vez só. Nas próximas vezes o sistema abre "
            "direto.",
            "p_pequeno",
        ),

        passo("5", "Use o sistema"),
        p(
            "O navegador abre sozinho no endereço "
            "<font face='Courier'><b>http://localhost:8000</b></font>. Se não abrir, "
            "digite esse endereço no navegador."
        ),
        p(
            "<b>Enquanto estiver usando o sistema, deixe a janela preta aberta.</b> "
            "É ela que mantém o programa funcionando. Para desligar, feche essa "
            "janela — e para usar de novo depois, clique duas vezes no mesmo arquivo "
            "INICIAR."
        ),
        aviso(
            "Não há segundo passo de instalação",
            "A partir daqui, o arquivo INICIAR é a única coisa que você precisa "
            "conhecer. Ele instala na primeira vez e apenas abre o sistema nas "
            "seguintes — é o mesmo clique nos dois casos.",
        ),
        p("Perguntas comuns nesse ponto", "h2"),
        tabela(
            ["Pergunta", "Resposta"],
            [
                ["Preciso estar conectado à internet?",
                 "Só na primeira vez, para baixar as bibliotecas. Depois o sistema "
                 "funciona sem internet."],
                ["Meus dados vão para algum servidor?",
                 "Não. Tudo fica em um arquivo dentro da própria pasta do sistema, no "
                 "seu computador."],
                ["Outra pessoa na rede consegue acessar?",
                 "Não. O sistema atende apenas o próprio computador."],
                ["Como faço cópia de segurança?",
                 "Copie o arquivo <font face='Courier'>precificacao.db</font>, dentro "
                 "da pasta <font face='Courier'>backend</font>. Ele contém todos os "
                 "seus dados."],
            ],
            [5.6 * cm, LARGURA_UTIL - 5.6 * cm],
        ),
    ]


def parte_uso() -> list:
    return [
        PageBreak(),
        p("Como começar a usar", "h1"),
        p(
            "A ordem abaixo não é arbitrária: cada passo depende do anterior. Tentar "
            "cotar antes de ajustar a tributação, por exemplo, produz um preço que o "
            "próprio sistema marca como estimativa."
        ),

        passo("6", "Confira os parâmetros da sua unidade"),
        p(
            "Vá em <b>Cadastros › Unidades e parâmetros</b>. Aqui ficam as decisões "
            "que valem para tudo: regime tributário, margem-alvo, contribuição mínima, "
            "taxa de capital e tolerância do balanço de massa."
        ),
        p(
            "Repare no rodapé de cada cartão: há uma <b>data de vigência</b>. "
            "Parâmetros não são editados por cima — alterar uma meta encerra a "
            "vigência atual e abre outra. É isso que permite reabrir uma cotação de "
            "seis meses atrás e obter exatamente o mesmo preço."
        ),
        tabela(
            ["Parâmetro", "O que ele decide"],
            [
                ["Margem-alvo", "A margem embutida no preço-alvo, sobre a receita líquida"],
                ["Contribuição mínima", "O piso de margem para ocupar capacidade ociosa"],
                ["Taxa de capital (a.a.)", "Quanto custa o dinheiro parado no ciclo financeiro"],
                ["Tolerância de massa", "Acima dessa divergência, o lote não encerra"],
            ],
            [4.8 * cm, LARGURA_UTIL - 4.8 * cm],
        ),

        passo("7", "Ajuste a tributação"),
        p(
            "Este é o passo mais importante, e o único que <b>precisa</b> ser feito "
            "antes de qualquer cotação valer. Vá em <b>Motor tributário › Matriz de "
            "regras</b>."
        ),
        p(
            "O sistema não usa um percentual único de imposto. Ele usa uma <b>matriz "
            "de regras</b>: cada linha diz em quais operações se aplica, como calcula "
            "e até quando vale. A regra usada em um cálculo é escolhida pela data da "
            "operação, nunca pela data de hoje."
        ),

        p("Criar uma regra", "h2"),
        p(
            "Clique em <b>Nova regra</b>. Os campos essenciais são o tributo, a "
            "operação, a alíquota e o fundamento legal. Mas o bloco que realmente "
            "decide o preço é o de <b>efeito econômico</b>:"
        ),
        tabela(
            ["Marcação", "O que o motor faz com ela"],
            [
                ["Deduz do preço (entra em r)",
                 "O tributo reduz a receita líquida da venda. É o caso de PIS, COFINS "
                 "e ICMS de saída — e, no Lucro Presumido, também da presunção de "
                 "IRPJ e CSLL."],
                ["Gera crédito na compra",
                 "O tributo pago na aquisição pode reduzir o custo — mas só se a "
                 "recuperabilidade for <i>elegível</i>. Crédito condicionado gera "
                 "alerta e não abate nada."],
                ["Compõe custo não recuperável",
                 "Regimes cumulativos: o tributo embutido na compra vira custo, sem "
                 "direito a crédito."],
                ["Incide sobre o lucro",
                 "IRPJ e CSLL no Lucro Real. Ficam <b>fora</b> de r, porque incidem "
                 "sobre o lucro apurado no período, não sobre a receita. A margem-alvo "
                 "passa a ser margem antes desses tributos."],
                ["Condicional",
                 "A regra só produz efeito quando alguém confirmar a condição. É o "
                 "caso do crédito da Lei 15.394/2026, que exige comprovar o uso do "
                 "material como matéria-prima."],
            ],
            [4.8 * cm, LARGURA_UTIL - 4.8 * cm],
        ),
        Spacer(1, 0.3 * cm),
        aviso(
            "Alíquotas são frações, não percentuais",
            "Digite <font face='Courier'>0.0925</font> para 9,25%, não "
            "<font face='Courier'>9.25</font>. Vale para alíquota, redução de base, "
            "presunção e margens. O sistema exibe o percentual formatado depois de "
            "salvar, então dá para conferir na hora.",
        ),

        p("Validar uma regra", "h2"),
        p(
            "Toda regra nasce <b>provisória</b> — inclusive as que você mesmo criar. "
            "Não existe caminho no sistema para criar uma regra já validada, e isso é "
            "de propósito: validar é um ato separado, de quem tem responsabilidade "
            "técnica sobre o número."
        ),
        p(
            "Clique em <b>Validar</b> na linha da regra. O sistema mostra alíquota, "
            "vigência e fundamento para conferência, e pede o nome de quem está "
            "validando. Esse nome e a data ficam gravados na regra."
        ),
        p(
            "Enquanto houver regra provisória aplicável a uma operação, a cotação "
            "aparece marcada como <b>apenas estimativa</b>. Depois de validadas, ela "
            "passa a poder ser definitiva."
        ),

        p("Alterar uma regra que já está valendo", "h2"),
        p(
            "Aqui o sistema impõe uma regra que costuma incomodar à primeira vista, e "
            "que existe por um bom motivo: <b>regra validada não pode ser editada no "
            "lugar</b>. O botão <i>Editar</i> simplesmente não aparece."
        ),
        p(
            "A razão: aquela regra pode ter sustentado um preço que alguém já "
            "praticou. Reescrever seus números apagaria a base de uma decisão "
            "comercial tomada — e a cotação antiga deixaria de ser reproduzível."
        ),
        p("Em vez disso, use <b>Nova vigência</b>. O sistema então:"),
        lista([
            "encerra a regra atual no dia anterior ao início da nova, para que as "
            "duas nunca valham ao mesmo tempo;",
            "cria uma sucessora com os novos valores e número de versão maior;",
            "marca a sucessora como <b>provisória</b>, porque a validação anterior "
            "se referia aos números anteriores;",
            "mantém a anterior no histórico, ainda validada — operações antigas "
            "continuam sendo calculadas com ela.",
        ]),
        Spacer(1, 0.3 * cm),
        p(
            "Se a regra apenas deixou de valer e não tem substituta, use "
            "<b>Encerrar</b>: você informa o último dia de vigência e o motivo."
        ),
        p("Resumindo o ciclo de vida:", "p_pequeno"),
        codigo(
            "  criar  ->  PROVISORIA  ---- validar ---->  VALIDADA",
            "               |  ^                             |",
            "           editar  |                     nova vigencia",
            "                   +------ sucessora <----------+",
            "                           (PROVISORIA, versao + 1)",
        ),

        passo("8", "Cadastre materiais e parceiros"),
        p(
            "Em <b>Cadastros › Materiais</b>, o que mais importa são o rendimento-"
            "padrão e a perda normal: são eles que o sistema usa para saber quanto de "
            "cada tonelada comprada vira produto vendável."
        ),
        p(
            "Em <b>Cadastros › Parceiros</b>, o regime tributário e a condição de "
            "contribuinte de ICMS não são dado cadastral decorativo — entram como "
            "chave na escolha da regra fiscal. Um cliente no Lucro Real, por exemplo, "
            "pode ativar a isenção da Lei 15.394/2026."
        ),

        passo("9", "Registre um lote e veja o resultado"),
        p(
            "Em <b>Operações › Lotes de compra</b>, clique em qualquer lote para ver "
            "a tela mais reveladora do sistema. Ela tem três blocos:"
        ),
        lista([
            "<b>Balanço de massa</b> — peso bruto, aceito e vendável são grandezas "
            "diferentes e aparecem separadas. O rendimento sai daí.",
            "<b>Composição do custo</b> — aquisição, transformação e capital de giro. "
            "Repare que o custo por quilograma vendável é maior que o por quilograma "
            "aceito: é assim que a perda é transferida ao produto que sobrou.",
            "<b>Memória de cálculo</b> — cada passo abre mostrando a fórmula, as "
            "entradas e a fonte. Dá para exportar em JSON e refazer a conta à mão.",
        ]),
        Spacer(1, 0.3 * cm),
        p(
            "Se a soma das saídas não bater com a quantidade aceita além da "
            "tolerância, o lote <b>não encerra</b>. A tela mostra a divergência em vez "
            "de escondê-la somando ao rendimento — porque essa diferença costuma ser "
            "furto, erro de balança ou apontamento faltando."
        ),

        passo("10", "Simule uma cotação"),
        p(
            "Em <b>Cotações</b>, preencha as premissas à esquerda e clique em "
            "<b>Simular</b>. O resultado traz:"
        ),
        lista([
            "<b>a escada de cinco preços</b>, do preço de caixa ao preço-alvo, cada "
            "um com sua finalidade escrita;",
            "<b>a avaliação da proposta</b>, se você informar um preço proposto: em "
            "que faixa ele cai, quanto vale a concessão e qual alçada precisa aprovar;",
            "<b>a composição do preço</b>, mostrando de onde vem cada centavo;",
            "<b>quatro cenários</b> — base, otimista, estressado e ponto de "
            "equilíbrio;",
            "<b>o preço máximo de compra</b>, que responde à pergunta mais útil "
            "quando o preço de venda é ditado pelo mercado: quanto posso pagar pelo "
            "material?",
        ]),
        Spacer(1, 0.3 * cm),
        p(
            "Mude qualquer premissa e clique em Simular de novo. Cada recálculo é "
            "feito pelo servidor, não na tela — o que aparece é sempre um número "
            "auditável, com memória de cálculo."
        ),

        passo("11", "Leia o painel gerencial"),
        p(
            "Em <b>Painel gerencial</b>, os indicadores do período. Dois pontos que "
            "diferenciam este painel de uma planilha comum:"
        ),
        lista([
            "<b>A ociosidade aparece separada.</b> A capacidade paga e não utilizada "
            "é custo do período, nunca do produto. Rateá-la nos lotes encareceria o "
            "produto justamente quando o volume caiu.",
            "<b>O que não pode ser calculado é declarado.</b> No fim da página há uma "
            "seção listando os indicadores que a base ainda não sustenta, com o "
            "motivo. Nenhum deles aparece zerado ou estimado.",
        ]),
    ]


def parte_referencia() -> list:
    return [
        PageBreak(),
        p("Regras que o sistema não relaxa", "h1"),
        p(
            "Em vários momentos o sistema vai recusar o que você pediu. Isso não é "
            "defeito — é a especificação funcionando. As mensagens sempre dizem a "
            "causa. As principais:"
        ),
        tabela(
            ["Quando acontece", "O que o sistema faz", "Por quê"],
            [
                ["Regra fiscal provisória ou vencida",
                 "A cotação sai marcada como estimativa",
                 "Preço definitivo exige regra validada, mesmo com todos os outros "
                 "campos preenchidos"],
                ["Balanço de massa fora da tolerância",
                 "O lote não encerra",
                 "A divergência costuma ser furto, erro de balança ou apontamento "
                 "faltando; somá-la ao rendimento esconderia o problema"],
                ["Crédito tributário condicionado",
                 "Não reduz o custo; gera alerta",
                 "Crédito só abate quando a condição for confirmada documentalmente"],
                ["Tentativa de editar regra validada",
                 "Recusa, com orientação de abrir nova vigência",
                 "A regra pode ter sustentado um preço já praticado"],
                ["Mesmo custo em pool de atividade e como lançamento direto",
                 "Recusa o cálculo",
                 "Seria dupla contagem: o custo entraria duas vezes no produto"],
                ["Preço abaixo da margem de contribuição",
                 "Bloqueia, exigindo decisão da diretoria",
                 "Abaixo desse ponto cada tonelada vendida consome caixa"],
            ],
            [4.6 * cm, 4.4 * cm, LARGURA_UTIL - 9 * cm],
        ),

        p("Se algo der errado", "h1"),
        tabela(
            ["O que aconteceu", "O que fazer"],
            [
                ["A janela abriu e fechou na hora",
                 "O Python não está instalado, ou foi instalado no Windows sem marcar "
                 "“Add Python to PATH”. Reinstale marcando essa caixa e tente de novo."],
                ["O navegador não abriu sozinho",
                 "Digite <font face='Courier'>localhost:8000</font> na barra de "
                 "endereços do navegador."],
                ["As telas abrem, mas dizem que não conseguem falar com o servidor",
                 "A janela preta foi fechada. Clique duas vezes no arquivo INICIAR "
                 "de novo."],
                ["Apareceu uma mensagem de erro em vermelho",
                 "As últimas linhas da janela explicam o que falhou. Guarde essas "
                 "linhas: elas dizem exatamente onde o processo parou."],
                ["Quero recomeçar do zero",
                 "Feche o sistema, apague o arquivo "
                 "<font face='Courier'>precificacao.db</font> da pasta "
                 "<font face='Courier'>backend</font> e clique em INICIAR de novo. "
                 "<b>Isso apaga todos os dados.</b>"],
            ],
            [6 * cm, LARGURA_UTIL - 6 * cm],
        ),

        p("Para quem cuida da instalação", "h1"),
        p(
            "Esta seção não é necessária para usar o sistema. Ela existe para quem "
            "for prepará-lo para uso profissional."
        ),
        lista([
            "<b>Banco de dados.</b> O sistema usa um arquivo SQLite dentro da pasta "
            "<font face='Courier'>backend</font>, o que dispensa instalar qualquer "
            "servidor de banco. Para uso com várias pessoas, aponte a variável "
            "<font face='Courier'>DATABASE_URL</font> para um PostgreSQL e rode "
            "<font face='Courier'>alembic upgrade head</font>; nenhuma outra "
            "alteração é necessária.",
            "<b>Cópia de segurança.</b> Copiar o arquivo "
            "<font face='Courier'>backend/precificacao.db</font> preserva todos os "
            "dados. Restaurar é colocar o arquivo de volta no mesmo lugar.",
            "<b>Documentação técnica da API.</b> Com o sistema aberto, o endereço "
            "<font face='Courier'>localhost:8000/api/docs</font> lista todos os "
            "endpoints e permite testá-los pelo navegador.",
            "<b>Alterar as telas.</b> Exige Node.js e recompilar a interface com "
            "<font face='Courier'>npm run build</font> dentro da pasta "
            "<font face='Courier'>frontend</font>. Quem apenas usa o sistema nunca "
            "precisa disso.",
        ]),
        Spacer(1, 0.4 * cm),

        p("Onde está o resto da documentação", "h1"),
        p(
            "Dentro do projeto, na pasta "
            "<font face='Courier'>sistema-precificacao/docs/</font>:"
        ),
        tabela(
            ["Arquivo", "O que traz"],
            [
                ["<font face='Courier'>especificacao.md</font>",
                 "O documento de requisitos completo que originou o sistema"],
                ["<font face='Courier'>dicionario-de-dados.md</font>",
                 "As tabelas do banco, o que cada campo significa e as convenções de unidade"],
                ["<font face='Courier'>motor-de-calculo.md</font>",
                 "Todas as fórmulas implementadas, com a seção da especificação de origem"],
                ["<font face='Courier'>api.md</font>",
                 "Os endpoints, os códigos de erro e exemplos de chamada"],
                ["<font face='Courier'>frontend.md</font>",
                 "A estrutura das telas e as decisões de interface"],
                ["<font face='Courier'>visualizacao.md</font>",
                 "As decisões de gráfico e a paleta de cores validada"],
            ],
            [6 * cm, LARGURA_UTIL - 6 * cm],
        ),
        Spacer(1, 0.5 * cm),
        p(
            "A documentação da API também está disponível de forma interativa em "
            "<font face='Courier'>localhost:8000/docs</font> com o servidor no ar: dá "
            "para testar qualquer endpoint direto pelo navegador."
        ),
    ]


# --------------------------------------------------------------- documento
def rodape(canvas, doc):
    """Numero de pagina e faixa de identificacao, exceto na capa."""

    canvas.saveState()
    if doc.page > 1:
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(TINTA_TENUE)
        canvas.drawString(
            2 * cm, 1.4 * cm,
            "Sistema de custeio e precificação para reciclagem — manual de instalação e primeiros passos",
        )
        canvas.drawRightString(A4[0] - 2 * cm, 1.4 * cm, str(doc.page))
        canvas.setStrokeColor(BORDA)
        canvas.setLineWidth(0.4)
        canvas.line(2 * cm, 1.8 * cm, A4[0] - 2 * cm, 1.8 * cm)
    canvas.restoreState()


def capa_fundo(canvas, doc):
    """Faixa verde no topo da capa."""

    canvas.saveState()
    canvas.setFillColor(VERDE)
    canvas.rect(0, A4[1] - 1.1 * cm, A4[0], 1.1 * cm, stroke=0, fill=1)
    canvas.setFillColor(VERDE_CLARO)
    canvas.rect(0, A4[1] - 1.4 * cm, A4[0], 0.3 * cm, stroke=0, fill=1)
    canvas.restoreState()


def gerar(caminho: str) -> None:
    doc = BaseDocTemplate(
        caminho,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2.4 * cm,
        title="Manual de instalação e primeiros passos — Sistema de precificação para reciclagem",
        author="Sistema de custeio e precificação para operações de reciclagem",
        subject="Instalação, configuração da matriz tributária e primeiros passos de uso",
    )

    quadro = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height, id="corpo",
    )
    doc.addPageTemplates([
        PageTemplate(id="capa", frames=[quadro], onPage=capa_fundo),
        PageTemplate(id="corpo", frames=[quadro], onPage=rodape),
    ])

    historia: list = []
    historia += capa()
    historia.append(NextPageTemplate("corpo"))
    historia.append(PageBreak())
    historia += parte_instalacao()
    historia += parte_uso()
    historia += parte_referencia()

    doc.build(historia)


if __name__ == "__main__":
    import sys

    destino = sys.argv[1] if len(sys.argv) > 1 else "manual.pdf"
    gerar(destino)
    print(f"gerado: {destino}")
