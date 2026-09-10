FastAPI
 0.1.0 
OAS3
/openapi.json
default


Schemas
Auxiliares{
resultados*	Resultados[...]
 
}
CNPJ{
cnpj_base*	Cnpj Base[...]
nome_empresarial	Nome Empresarial[...]
natureza_juridica	Natureza Juridica[...]
qualificacao_responsavel	Qualificacao Responsavel[...]
capital_social*	Capital Social[...]
porte_empresa	Porte Empresa[...]
ente_federativo	Ente Federativo[...]
cnpj_ordem*	Cnpj Ordem[...]
cnpj_dv*	Cnpj Dv[...]
identificador	Identificador[...]
nome_fantasia	Nome Fantasia[...]
situacao_cadastral	Situacao Cadastral[...]
data_situacao_cadastral	Data Situacao Cadastral[...]
motivo_situacao_cadastral	Motivo Situacao Cadastral[...]
nome_cidade_exterior	Nome Cidade Exterior[...]
pais	Pais[...]
data_inicio_atividade	Data Inicio Atividade[...]
cnae_fiscal_principal	Cnae Fiscal Principal[...]
cnaes_fiscais_secundarios	Cnaes Fiscais Secundarios[...]
tipo_logradouro	Tipo Logradouro[...]
logradouro	Logradouro[...]
numero	Numero[...]
complemento	Complemento[...]
bairro	Bairro[...]
cep	Cep[...]
uf	Uf[...]
municipio	Municipio[...]
ddd1	Ddd1[...]
telefone_1	Telefone 1[...]
ddd2	Ddd2[...]
telefone_2	Telefone 2[...]
fax	Fax[...]
ddd_fax	Ddd Fax[...]
correio_eletronico	Correio Eletronico[...]
situacao_especial	Situacao Especial[...]
data_situacao_especial	Data Situacao Especial[...]
opcao_simples	Opcao Simples[...]
data_opcao_simples	Data Opcao Simples[...]
data_exclusao_simples	Data Exclusao Simples[...]
opcao_mei	Opcao Mei[...]
data_opcao_mei	Data Opcao Mei[...]
data_exclusao_mei	Data Exclusao Mei[...]
natureza_juridica_desc	Natureza Juridica Desc[...]
motivo_situacao_desc	Motivo Situacao Desc[...]
municipio_desc	Municipio Desc[...]
pais_desc	Pais Desc[...]
cnae_fiscal_principal_descricao	Cnae Fiscal Principal Descricao[...]
identificador_descricao	Identificador Descricao[...]
porte_empresa_descricao	Porte Empresa Descricao[...]
situacao_cadastral_descricao	Situacao Cadastral Descricao[...]
socios	Socios[...]
 
}
CnaesFiscaisSecundario{
codigo*	Codigo[...]
descricao	Descricao[...]
 
}
Count{
total*	Total[...]
 
}
EmpresaPaginacaoItem{
cnpj_base*	Cnpj Base[...]
nome_empresarial	Nome Empresarial[...]
 
}
Estabelecimento{
cnpj_base*	Cnpj Base[...]
cnpj_ordem*	Cnpj Ordem[...]
cnpj_dv*	Cnpj Dv[...]
identificador	Identificador[...]
nome_fantasia	Nome Fantasia[...]
situacao_cadastral	Situacao Cadastral[...]
data_situacao_cadastral	Data Situacao Cadastral[...]
motivo_situacao_cadastral	Motivo Situacao Cadastral[...]
nome_cidade_exterior	Nome Cidade Exterior[...]
pais	Pais[...]
data_inicio_atividade	Data Inicio Atividade[...]
cnae_fiscal_principal	Cnae Fiscal Principal[...]
cnaes_fiscais_secundarios	Cnaes Fiscais Secundarios[...]
tipo_logradouro	Tipo Logradouro[...]
logradouro	Logradouro[...]
numero	Numero[...]
complemento	Complemento[...]
bairro	Bairro[...]
cep	Cep[...]
uf	Uf[...]
municipio	Municipio[...]
ddd1	Ddd1[...]
telefone_1	Telefone 1[...]
ddd2	Ddd2[...]
telefone_2	Telefone 2[...]
ddd_fax	Ddd Fax[...]
fax	Fax[...]
correio_eletronico	Correio Eletronico[...]
situacao_especial	Situacao Especial[...]
data_situacao_especial	Data Situacao Especial[...]
 
}
EstabelecimentoPaginacaoItem
HTTPValidationError
ItemAuxiliar{
descricao*	Descricao[...]
codigo*	Codigo[...]
 
}
PaginacaoEmpresas{
limite_resultados_paginacao*	Limite Resultados Paginacao[...]
resultados_paginacao*	Resultados Paginacao[...]
 
}
PaginacaoEstabelecimentos{
limite_resultados_paginacao*	Limite Resultados Paginacao[...]
resultados_paginacao*	Resultados Paginacao[...]
 
}
PaginacaoSocios{
limite_resultados_paginacao*	Limite Resultados Paginacao[...]
resultados_paginacao*	Resultados Paginacao[...]
 
}
Socio{
identificador_entidade	Identificador Entidade[...]
nome	Nome[...]
cnpj_cpf	Cnpj Cpf[...]
qualificacao_descricao	Qualificacao Descricao[...]
qualificacao_codigo	Qualificacao Codigo[...]
data_entrada_sociedade	Data Entrada Sociedade[...]
pais	Pais[...]
cpf_representante	Cpf Representante[...]
nome_representante	Nome Representante[...]
qualificacao_representante_codigo	Qualificacao Representante Codigo[...]
qualificacao_representante_descricao	Qualificacao Representante Descricao[...]
faixa_etaria_codigo	Faixa Etaria Codigo[...]
faixa_etaria_descricao	Faixa Etaria Descricao[...]
identificador_entidade_descricao	Identificador Entidade Descricao[...]
 
}
SocioPaginacaoItem{
cnpj_base*	Cnpj Base[...]
nome	Nome[...]
cnpj_cpf	Cnpj Cpf[...]
 
}
ValidationError{
loc*	Location[...]
msg*	Message[...]
type*	Error Type[...]
 
}