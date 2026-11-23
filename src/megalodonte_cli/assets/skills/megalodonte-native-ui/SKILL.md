---
name: megalodonte-native-ui
description: Criar ou refatorar interfaces Megalodonte com composição declarativa e State; aplicar as APIs específicas de desktop, Android ou Roku.
---

# Interface Megalodonte

Para live reload de aplicativos desktop nativos, use `megalodonte dev --project .`
quando o CLI e core/base atualizados estiverem disponíveis. Não substitua blocos
de memória nem class loaders para simular uma troca segura: o agente aplica
redefinições suportadas pela JVM e rerenderiza telas gerenciadas, preservando
instâncias e State. `render()` deve gerar uma raiz nova, sem efeitos de domínio;
assinaturas síncronas são descartadas por `SubscriptionScope` (incluindo reactivity
atualizada). Recursos e assinaturas assíncronas precisam de ciclo de vida próprio.
Mudanças estruturais (novos métodos `static`, campos, classes, assinaturas ou
dependências) fazem o comando padrão reiniciar automaticamente o processo cliente;
esse fallback perde o estado em memória. Antes de encerrar o processo antigo, o
CLI solicita um snapshot JSON das janelas gerenciadas. O novo processo restaura
posição, tamanho, modo maximizado/tela cheia/minimizado, visibilidade e a intenção
de foco. Se o aplicativo estava atrás de outro, não deve solicitar foco e envia
as janelas recriadas para trás. JavaFX não restaura portavelmente a posição exata
no z-order do sistema; Wayland pode impedir esse controle. Janelas secundárias só
reaparecem quando o startup volta a criá-las no mesmo papel/ordem; isso não migra
estado de domínio. A opção
`--no-restart-on-incompatible` mantém a geração anterior ativa. Documente esses limites e
não apresente reinício de processo como hot reload com estado preservado. JSONC,
builds multimódulo e janelas fora de Context/ScreenManager exigem integração própria.

A mensageria do mundo de compilação representa qualquer projeto por um manifesto
JSON inicial e deltas posteriores de arquivos, tokens e símbolos. Ela não deve
conhecer telas, entidades ou regras de uma aplicação consumidora. Conteúdos ficam
num armazenamento local por hash; recursos binários não devem virar Base64 no
JSON. A resposta contém status, diagnósticos e metadados dos artefatos compilados,
em vez de devolver a aplicação inteira. `.env` participa apenas com caminho,
tamanho e hash, nunca com valores, e sua alteração exige reinício. Tokenização
serve para detectar e classificar mudanças; não prometa compilar ou substituir um
campo Java isoladamente, pois javac e a JVM operam com unidades/classes e suas
dependências. Documente separadamente compilação, ativação e preservação de janela.

Dependências por builds compostos (`includeBuild`) são suportadas; o aplicativo
supervisionado ainda deve ser de projeto único. As bibliotecas mantêm suas saídas
próprias e entram como dependências congeladas; mudanças nas fontes delas exigem
parar/iniciar a sessão. Ao alterar integração Gradle, valide também um consumidor
com `includeBuild`: init scripts se propagam aos builds incluídos e devem conferir
a pasta canônica do alvo antes de alterar saídas, registrar tarefas ou exigir
plugins. Um teste isolado sem dependências locais não cobre essa configuração.
Valide também recompilações sucessivas após editar código, com dependências
aninhadas e chamadas reais às APIs delas; confira que os JARs mantêm suas classes.
No live reload, preserve os caches próprios de cada build Gradle: não imponha um
único `--project-cache-dir` à composição. Isolar os artefatos compilados não exige
compartilhar o histórico incremental entre builds.

Preservar janelas no live reload significa manter os mesmos Stage/Scene, não
fechar e reabrir janelas semelhantes. Janelas secundárias gerenciadas precisam
ser registradas explicitamente no ciclo de montagem e removidas no fechamento;
não dependa apenas de `Window.getWindows()`. Valide a atualização com a janela
secundária já criada e confira identidade de Stage/Scene, estado e montagem.
O protótipo `NativeWindowHost` do base mantém
janelas em um hospedeiro e troca workers Java por mensagens JSON internas; isso
continua sendo modo nativo, não construção de UI JSONC. Ainda exige API explícita,
tem cobertura limitada de controles e usa a opção experimental
`megalodonte dev --native-host --worker-main pacote.WorkerMain`. Não adapta o Main
normal ou telas existentes automaticamente. Não afirme migração automática de estado de negócio. Consulte
`docs/NATIVE_MESSAGING.md` do base para status, limites e testes de identidade.
Esse protótipo de UI/worker é separado do protocolo projeto-compilador e não deve
ser apresentado como a implementação da mensageria incremental da aplicação toda.

Esta skill é compartilhada entre projetos desktop, Android e Roku. A composição declarativa, o tema e a separação de lógica orientam todas as plataformas. As regras abaixo que citam JavaFX, `megalodonte-components-desktop` ou `disgust-components` são específicas de desktop. No Android, adapte estado e composição às APIs da bridge; na Roku, use `megalodonte-roku` (inclusive seu `Counter` de runtime), sem presumir que `State` ou componentes desktop estejam disponíveis. Consulte o código da plataforma antes de aplicar uma API citada abaixo.

Ao evoluir APIs equivalentes entre plataformas, coloque no `megalodonte-core` apenas contratos e comportamento sem dependências nativas. Faça as implementações desktop e Android declararem os mesmos contratos, preservando lifecycle e renderer próprios; métodos `static` de fábrica continuam específicos porque Java não os sobrescreve. Aplique essa fronteira progressivamente a reatividade, componentes, props, router e novos módulos. Artefatos neutros ficam sem sufixo; todo artefato específico deve terminar em `-desktop` ou `-android`, como `megalodonte-components-desktop` e `megalodonte-base-android`.

Em Android, listas reativas combinam `ListState` (que é um `ReadableState<List<T>>`) com `Column.items(...)` ou `Row.items(...)` e um mapper que devolve uma instância nova por item; cada mudança recria as views do bloco, sem reconciliação nem preservação de foco. Alterações de `State`/`ListState` devem ocorrer na thread principal: ao retornar de thread de fundo, executor ou callback assíncrono, encaminhe a atualização por `megalodonte.base.UI.runOnUi(...)`, que usa o `Handler` do looper principal e executa na hora quando já está nele. A bridge recusa comandos fora da thread principal. Prefira preencher estados em `onMount()`, quando as assinaturas já estão ativas, e consulte `docs/CLIENT_API.md` do `megalodonte-android` para a API real da plataforma.

Ao adicionar AndroidX ou Material Components a um módulo do framework Android,
habilite também `android.useAndroidX=true` no `gradle.properties` de cada projeto
consumidor afetado e no modelo Android do `megalodonte-cli`. A propriedade do
checkout do framework não se propaga ao build raiz que inclui seus módulos.
Valide o aplicativo consumidor e um projeto recém-gerado; compilar apenas o
framework não detecta essa ausência.

Nos workflows Android, use `android-actions/setup-android@v4` e instale
explicitamente a plataforma e o build-tools requeridos com `sdkmanager`. Não
reintroduza a v3: em runners atuais ela pode tentar instalar implicitamente o
pacote obsoleto `tools` e falhar antes de executar o Gradle. Ao corrigir um
projeto antigo, confira também o template do `megalodonte-cli` para que projetos
novos não repitam a configuração defeituosa.

No Android, `megalodonte.components.Switch` mantém o construtor desktop
`Switch(String label, State<Boolean>)` e usa um `MaterialSwitch` nativo. Use-o
para ativar ou desativar imediatamente uma configuração ou recurso; use
`Checkbox` para seleção/confirmação quando a mudança não representa um toggle
imediato. O primeiro argumento do `Switch` é o rótulo visível junto ao controle e
também sua descrição acessível; não duplique a legenda com um `Text` separado.
O rótulo usa `theme.colors().textPrimary()` por padrão; personalize um caso
específico com `new SwitchProps().textColor(...).fontSize(...)`, sem acessar o
widget Android nativo.
Para efeitos decorrentes do toque, encadeie
`.onCheckedChange(currentState -> ...)`: o callback recebe o novo valor depois
que o `State<Boolean>` foi atualizado. Mudanças programáticas no `State` devem
atualizar o controle sem executar esse callback de interação do usuário.

No renderer Android, wrappers condicionais como `Show.when` não devem envolver
uma `Column` em `WRAP_CONTENT` quando seus inputs ou botões usam largura
`MATCH_PARENT`: isso colapsa a largura interna, preserva somente a altura e
aparece como espaço branco. O `Show` dentro de uma `Column` e seu ramo renderizado
devem preencher a largura disponível; dentro de uma `Row`, preserve largura de
conteúdo salvo configuração explícita.

Para saídas extensas, logs ou análise de código, use o context-mode quando ele realmente reduzir o contexto necessário; para consultas curtas, prefira buscas diretas e concisas. A preferência e as salvaguardas estão na skill `criterioso`.

Construa a árvore de componentes de forma declarativa. `render()` e as fábricas de componentes retornam a expressão composta, com `children(...)` ou APIs reativas da biblioteca. Não monte uma árvore por etapas com variáveis de componentes, `getChildren().add(...)` ou `clear()` para depois retorná-la. Uma variável local pode representar um valor ou uma condição; não deve ser o mecanismo normal de montagem da UI.

Trate a árvore como uma projeção do estado, inclusive quando os dados chegam de forma assíncrona. Prefira `State`, `ComputedState`, `ListState`, `Show.when(...)` e `ForEachState` para expressar carregamento, visibilidade, filtros e listas. O serviço ou a ViewModel atualiza os estados; a composição apenas descreve quais componentes Megalodonte aparecem para cada estado. Não replique esse mecanismo com `Platform.runLater`, listeners de propriedades JavaFX, flags mutáveis, `setVisible`/`setManaged` e inclusão ou remoção manual de filhos.

Por exemplo, uma seção remota que só deve existir após o carregamento pode retornar `Show.when(carregado, () -> new Row().items(ForEachState.of(itens, Components::card), 10))`. O exemplo representa o princípio, não uma assinatura universal: confira a API real e mantenha tratamento de falhas, cache e ciclo de vida na camada dona dos dados. Evite pré-carregar `javafx.scene.image.Image` na tela apenas para controlar sua revelação; use o componente Megalodonte de imagem e, se ele ainda não expuser estado de carregamento ou erro necessário ao produto, evolua o componente compartilhado.

```java
private final State<String> nome = State.of("");

@Override public Component render() {
    return new Column(new ColumnProps().spacingOf(12)).children(
        new Text("Nome"),
        new Input(nome, new InputProps().placeHolder("Digite o nome"))
    );
}
```

Declare `State`, `ListState` e estados derivados como campos no topo da classe dona do estado, antes dos métodos. Não crie `State` dentro de `render()` ou de fábricas chamadas pela renderização: uma nova renderização perderia o valor e as inscrições. Se a tela acumular muitos estados, cálculos, carregamento ou ações, transfira essa lógica para uma `ViewModel`; a tela recebe a ViewModel e apenas descreve a árvore. Use binding e componentes reativos para mudanças de dados e coleções, em vez de alterar manualmente os filhos da árvore.

Para coleções reativas, use sempre `ListState<T>` em vez de
`State<List<T>>`. Inicialize coleções vazias com `ListState.ofEmpty()` e use
`ListState.of(lista)` quando houver valores iniciais. Além de tornar explícita a
semântica de coleção, isso preserva as operações reativas próprias de lista e
mantém o mesmo padrão entre desktop e Android.

```java
private final ListState<Categoria> categorias = ListState.ofEmpty();
```

Não chame `getJavaFxNode()` em código de aplicativo, inclusive para estilo, foco, seleção, eventos, tamanho ou inserção de filhos. Não instancie `javafx.scene.control` nem `javafx.scene.layout` em telas. Se a API de um componente não expõe uma operação necessária, avalie a possibilidade de expressá-la com `State` ou `Props`; se faltar uma capacidade reutilizável, implemente-a na biblioteca e consuma a nova API. JavaFX permanece dentro das bibliotecas como detalhe de implementação.

Em desktop, telas dedicadas de quiosque, mídia ou PDV que devam sempre ocupar o
monitor usam o metadado de rota `new RouteProps(width, height, title, resizable,
true)`. Não acesse `ScreenContext.selfStage()` apenas para chamar
`Stage.setFullScreen(...)`: o roteamento deve aplicar e restaurar o modo da
janela, inclusive na rota inicial, na navegação e após reinícios do live reload.
Quando a própria interface permitir sair e voltar à tela cheia, use
`ScreenContextInterface.toggleFullScreen()` (ou `setFullScreen(boolean)`) no
callback do botão; não manipule o `Stage` diretamente. O metadado da rota define
o modo inicial, enquanto o contexto representa a ação explícita do usuário.

Ao revisar uma UI, complexidade acidental é um sinal arquitetural: uma classe que mantém `VBox`/`HBox`/`FlowPane`, converte componentes com `CreateFromJavaFxNode`, cria `Label`/`ImageView`, injeta CSS inline, registra listeners e limpa filhos no `close()` provavelmente está reimplementando composição e reatividade fora do Megalodonte. Compare-a com uma fábrica declarativa que recebe estados e dados e retorna `Component`; prefira a segunda quando preserva o comportamento. Só mantenha a ponte JavaFX quando houver uma lacuna concreta e localizada na biblioteca, documentando-a e abrindo caminho para mover a capacidade reutilizável ao componente compartilhado.

Para abrir links externos no navegador, use `megalodonte.base.Redirect.to(url)` ou `Redirect.to(url, onError)`. Não use `Desktop.getDesktop().browse(...)`, `URI.create(...)` nem crie threads na tela para essa finalidade; `Redirect` já encapsula a abertura assíncrona. O callback de erro é executado fora da thread de UI: se ele apresentar um alerta ou atualizar estado visual, encaminhe essa parte por `UI.runOnUi(...)`.

Em aplicativos desktop, registre `ErrorReporter.register(...)` no início do bootstrap, antes de iniciar tarefas com `Async.Run`, `Scope` ou navegação que possa falhar. O callback central recebe o `Throwable` e pertence ao aplicativo: ele pode registrar logs, apresentar um alerta pela abstração visual do projeto ou notificar um serviço externo. Como pode ser chamado fora da thread JavaFX, toda apresentação visual deve passar por `UI.runOnUi(...)`. Encaminhe exceções capturadas que devam seguir a mesma política com `ErrorReporter.handle(error)`; não espalhe tratamentos divergentes quando a falha pertence à política global. O framework também grava as falhas reportadas em `~/.megalodonte/errors.log`.

Em aplicativos desktop Linux com ícone próprio, configure `MegalodonteApp.appIcon("/icon.png")` antes de iniciar e use uma subclasse exclusiva de `MegalodonteApplication` em `MegalodonteApp.run(AppHost.class, args, ...)`. O `WM_CLASS` dessa classe permite ao dock associar a janela ao `.desktop` correto; o framework deve usar um novo caminho de ícone quando o conteúdo mudar para evitar imagem antiga em cache. Confirme o resultado no aplicativo efetivamente iniciado, não apenas no recurso do projeto.

Use os valores e padrões do tema via `ThemeManager` e `Props`. Preserve as cores padrão dos componentes sempre que possível. Uma identidade visual realmente exclusiva, como marca, pode ter tokens próprios no tema do aplicativo; evite hexadecimais e CSS inline espalhados pelas telas. Quando uma opção de estilo ou tamanho é recorrente, modele-a em `Props` ou num componente reutilizável.

Não guarde `Column`, `Row`, `Container`, `Stack` ou outro componente como campo da tela. Se uma operação imperativa for realmente inevitável e não puder ser modelada por estado, guarde `Ref<T>` como campo e vincule a referência ao componente criado na árvore. `Ref` é exceção para casos como foco; não é substituto de `State` nem justificativa para manter uma árvore mutável.

`State.subscribe(...)` e `ListState.subscribe(...)` notificam imediatamente com
o valor atual. Não acesse nesse callback uma `Ref` que só será preenchida pelo
`render()`: durante o construtor ela ainda será nula. Também não use
`ref.current().children(...)` para trocar uma subárvore já montada, pois mutar o
modelo não solicita reconciliação à bridge. Expresse a troca com componentes
reativos suportados, como `Show.when(...)` ou `Column.items(ListState, mapper)`;
para uma única tela dinâmica, uma lista com um item pode representar o ramo atual.

Coloque composições reutilizáveis em uma classe `Components` com métodos de fábrica `static` que recebem estado, dados e callbacks e **retornam** o componente pronto. Não mantenha componentes mutáveis globais nessa classe. Separe lógica de domínio, serviços e ViewModel da composição da UI.

Em projetos que usam ORM ou mapper relacional, mantenha as classes de
persistência em um pacote explícito `entities` (por exemplo,
`app.data.entities`), separado dos records ou modelos de domínio exibidos na
UI. Para entidades JavaBean com muitos campos, prefira Lombok `@Getter` e
`@Setter` a accessors mecânicos escritos à mão, desde que o projeto já use
Lombok. Preserve o mecanismo de migrations existente: não substitua Flyway por
`CREATE TABLE IF NOT EXISTS` espalhado no código nem troque Persism por JDBC
manual durante uma migração de UI sem uma decisão arquitetural explícita.

Ao criar ou alterar interfaces, mantenha a documentação do projeto atualizada durante o trabalho, sem esperar solicitação: registre comportamento implementado, decisões, limitações e próximos passos nos arquivos `docs/CONTEXT.md`, `docs/DECISIONS.md` e `docs/TODO.md` quando adotados pelo projeto; atualize também a documentação de uso afetada. Não apresente funcionalidade planejada ou parcial como concluída.

Quando a UI expõe uma sintaxe, ação ou estado pouco óbvio, explique-a junto ao controle com texto ou tooltip. Tooltips devem esclarecer o efeito do controle no contexto atual, sem substituir um exemplo completo no README. Confira a interface com os dados realmente carregados; a existência de um fluxo no repositório não demonstra que ele aparece na tela. Ao compartilhar recursos entre desktop e Android, compare os valores de tema e configuração efetivamente usados nas duas plataformas, respeitando as APIs de cada uma.

Em formulários de operações, apresente apenas os campos aplicáveis à operação escolhida, com nomes que indiquem os dados manipulados e exemplos concretos de caminhos ou referências. Evite expor opções internas ou de compatibilidade como campos sem explicação. Confira contraste dos valores selecionados no tema escuro e o acesso a todo o conteúdo de painéis, inclusive em janelas menores ou com rolagem.

Tooltips de componentes reutilizáveis devem ficar ancorados ao componente, preferencialmente abaixo dele quando houver espaço, e não encobrir o texto sob o ponteiro. Ao alterar essa regra, implemente-a na biblioteca compartilhada e siga seu fluxo de publicação local; descreva no tooltip a finalidade do botão específico.

No desktop, textos de instrução longos precisam caber na largura disponível. Use `TextFlow` de `megalodonte-components-desktop` envolvendo `Text` quando um parágrafo puder ultrapassar a janela, por exemplo `new TextFlow(new Text("Instruções..."))`. Confira o resultado em uma janela estreita; não dependa de uma linha única de `Text` nem de aumentar a largura da janela para esconder o problema. Essa orientação é específica da API desktop; consulte os componentes de texto da plataforma em Android e Roku.

Em editores de fluxos, mantenha visíveis no diagrama as decisões, navegação, mensagens e configurações que pertencem ao projeto; componentes reutilizáveis fornecem o mecanismo, não regras ocultas do bot. Para migrações, preserve entradas, respostas, estado persistido, destinatários e confirmação de envio; uma action que apenas chama uma classe legada não é migração completa. Use componentes de dados e composição quando disponíveis, e registre dependências e capacidades ainda faltantes sem prometer que tudo já aparece na UI.

Em prévias, dados fixos e imagens locais podem ilustrar campos dinâmicos; identifique quando forem exemplos e não os apresente como dados reais. Ao permitir duplicar ou excluir componentes conectados, preserve o trabalho relacionado e explique no controle o que acontece com conexões e subfluxos. Valide edição, salvamento e reabertura quando houver ambiente disponível; testes de interface ignorados não provam o comportamento.

Modele a interface a partir do estado real: uma ação iniciar/parar deve ter um único controle que muda de rótulo e função; painéis de seleção e espaços reservados devem aparecer apenas quando há conteúdo utilizável, e uma única peça deve aproveitar a largura disponível. Quando uma operação demorada acontece, exponha progresso, sucesso e falha no aplicativo e nos logs da execução por terminal. Configurações que alteram processamento devem persistir e ser lidas tanto na prévia quanto na saída final; verifique os dois caminhos.

Em tabelas, Esc pode limpar a seleção, mas não limpe globalmente ao clicar fora: botões de ação também ficam fora da tabela e precisam ler o item selecionado. Exponha `clearSelection()` na biblioteca e use uma ação ou região neutra explícita quando a tela precisar desmarcar; `Ref<SimpleTable>` permite que essa região acesse a instância renderizada sem chamar `getJavaFxNode()`. Para listagens longas, use a paginação da tabela existente; filtre o conjunto completo antes de paginar e mantenha os controles de navegação junto à tabela. Ao atualizar os dados, ajuste a página atual se ela deixar de existir e valide seleção, pesquisa e ações sobre o item visível.

Geração de PDF, acesso a disco pesado, rede e abertura de arquivos ou aplicativos externos não devem executar na thread JavaFX. Faça uma cópia dos dados necessários antes de iniciar o trabalho em segundo plano; retorne alertas e mudanças visuais por `UI.runOnUi(...)`. Um visualizador externo pode bloquear ou faltar no sistema: registre o caminho do arquivo e a falha, e ofereça uma mensagem compreensível ao usuário. Se o usuário pedir teste visual, teste o fluxo pelo clique real quando houver ambiente gráfico; compilação e teste da função de exportação isolada não demonstram que a janela continua responsiva.
Em aplicações Megalodonte que dependem de `pack-utilities`, gere PDFs orientados
a dados com `pack.utilities.pdf.DataPdf` e um template JSONC versionado em
`src/main/resources/pdf`. Mapeie o domínio para dados simples e mantenha layout,
fontes, tabelas e repetições no template; não reintroduza uma classe que desenha
o documento manualmente nem use uma API de PDF de baixo nível na tela.


Antes de adicionar um componente desktop, procure equivalentes em `megalodonte-components-desktop` e `disgust-components` e confira a API atual no código-fonte. Componentes gerais de layout, entrada e dados pertencem ao artefato de componentes da plataforma; identidade visual e controles específicos de Disgust pertencem a `disgust-components`. Crie a peça faltante na biblioteca adequada e use-a na aplicação. Preserve o comportamento e os dados existentes durante uma refatoração.

Ao alterar código de uma biblioteca, rode seus testes e `./gradlew publishToMavenLocal` no repositório dela; não repita testes de outras aplicações consumidoras sem pedido explícito do usuário. `includeBuild` permite testar a fonte local, mas não atualiza o artefato que outros projetos obtêm de `mavenLocal()`. Publicação remota e `git push` seguem suas próprias autorizações e regras do workspace.

Depois de concluir uma alteração e obter sucesso nos testes pertinentes, faça commit nos repositórios alterados quando as regras de Git do workspace permitirem. Para bibliotecas, publique primeiro em Maven Local e confira a integração no projeto-alvo; só então faça o commit. Não rode testes de outras aplicações sem pedido explícito. Confira o diff e o status de cada repositório para não incluir mudanças alheias. Commit local não autoriza `git push`: respeite as restrições de horário e a autorização de envio aplicáveis.

Ao corrigir um campo ou componente, busque usos equivalentes no aplicativo e nos consumidores relevantes e corrija o mesmo defeito onde ele ocorrer. Compare o significado dos dados antes de aplicar uma máscara indiscriminadamente: quantidade, valor monetário e medidas podem exigir escalas diferentes. Valide os usos afetados no projeto-alvo; testes de outras aplicações exigem pedido explícito.

Em campos brasileiros formatados, use `pack.utilities.FormatterPack` como fonte das máscaras (CPF, CNPJ, CPF/CNPJ, CEP, telefone e moeda) por meio dos componentes existentes. Se faltar um campo reutilizável, implemente-o na biblioteca adequada usando o mesmo `FormatterPack`, em vez de duplicar a máscara na tela. Confira o contrato do `State`: alguns componentes guardam o valor sem pontuação, e `InputColumnCurrency` guarda centavos. Adapte o valor ao modelo de domínio quando necessário, sem alterar silenciosamente seu significado.

Em aplicativos desktop que já dependem de `disgust-components`, use
`InputsPack`, `disgust.io.Pack` e `disgust.io.br.Pack` como entrada padrão dos
campos de formulário. Escolha o componente pelo significado do dado: texto
livre, inteiro, decimal, data, CPF/CNPJ, telefone ou CEP. Não use um `Input`
genérico para quantidade, valor ou data e tente corrigir somente no `salvar`;
o componente deve impedir caracteres incompatíveis enquanto o usuário digita.
Para opções carregadas de forma assíncrona, preserve o `ListState`/`ReadableState`
no select em vez de capturar uma lista estática. Não aplique máscaras a campos
que semanticamente continuam sendo texto livre.

Quando uma seleção puder ter muitas opções ou precisar ser localizada por nome,
código ou outra apresentação textual, use o modo pesquisável do componente
genérico: `new Select<T>().items(items).value(selected).displayText(mapper).searchable()`
ou `new SelectProps().searchable()`. A busca pertence ao
`megalodonte-components-desktop`, pois é comportamento de entrada e seleção;
não crie um controle específico no aplicativo nem o coloque no Disgust apenas
por causa do estilo visual. Preserve o objeto tipado como valor selecionado e
filtre somente seu texto de apresentação.
No tema escuro, estilize também o editor interno desse controle e remova a área
legada separada do botão de seta quando o modo pesquisável já oferece abertura
pelo campo. Se a busca não produzir opções, feche o popup em vez de exibir uma
lista branca vazia.

Modais de formulário devem fechar por `Esc`, pelo botão de fechar e pela ação
Cancelar. Implemente `Esc` no componente `Modal` compartilhado, consumindo o
evento somente quando o overlay estiver visível, em vez de repetir handlers nas
telas consumidoras.

Um `Switch` deve exibir trilho arredondado e polegar móvel reais, nunca glifos
de texto para representar ligado/desligado. Mantenha o rótulo visível e
acessível no próprio componente, sem duplicá-lo com um `Text` externo. Em
formulários horizontais, não envolva inputs de largura preferida/fixa em filhos
com `fillWidth()`: isso cria grandes vazios entre campos sem ampliar o controle.
Use uma largura padrão comum para campos equivalentes e deixe `Row`/`FlowRow`
controlar espaçamento e quebra.

Em tabelas, formate a projeção visual de documentos, telefones, CEP, datas,
moedas e decimais com os formatadores compartilhados, sem alterar o valor bruto
do domínio ou da persistência. Em aplicativos com `disgust-components`, ações
recorrentes devem usar `ButtonsPack` e ícones: Novo/Salvar como ação contida,
Editar/Cancelar como delineada e Excluir como delineada de perigo. Estenda o
mesmo padrão a ações semanticamente equivalentes, preservando botões de
navegação com identidade visual própria quando houver decisão de design.

Ações destrutivas disparadas por tabelas ou listagens devem validar a seleção e
pedir confirmação explícita em diálogo antes de alterar a persistência. O botão
Cancelar do diálogo não pode chamar ViewModel, serviço ou repositório. Evite
abrir confirmação quando nada está selecionado; nesse caso, mostre diretamente
a orientação de seleção já definida pela tela.

Não tire capturas de tela para conferir a interface, salvo pedido explícito do usuário. Antes de concluir, revise os arquivos de tela em busca de `getJavaFxNode`, `getChildren().add`, controles JavaFX nativos, CSS inline, `State.of` dentro de `render()` e campos de componentes. Se algum caso excepcional permanecer, explique-o explicitamente e não declare a tela conforme ao padrão.
