/**
 * リソース命名規約と環境型の単一定義 (R-5)。
 *
 * `memoru-<env>-<suffix>` 形式のリソース名 / CloudFormation Export 名が各スタックに
 * ハードコードされ、`type Environment` も 3 ファイルで重複定義されていた。本モジュールに
 * 集約することで、プロジェクト名変更や命名スキーム変更をコンパイラ支援付きの一括変更にする。
 */

/** 全スタック共通の環境型（重複定義を解消）。 */
export type Environment = 'dev' | 'staging' | 'prod';

/** プロジェクト共通のリソース名プレフィックス。 */
const PROJECT = 'memoru';

/**
 * 環境付きリソース名を生成する。
 *
 * @example resourceName('dev', 'vpc') // => 'memoru-dev-vpc'
 */
export function resourceName(environment: Environment, suffix: string): string {
  return `${PROJECT}-${environment}-${suffix}`;
}

/**
 * CloudFormation Export 名を生成する。
 *
 * リソース名と同一の命名規約（`memoru-<env>-<suffix>`）だが、Export は別の名前空間で
 * あることを呼び出し側で明示できるようエイリアスとして公開する。
 *
 * @example exportName('dev', 'vpc-id') // => 'memoru-dev-vpc-id'
 */
export const exportName = resourceName;

/** prod 環境かどうかを判定する共通ヘルパー。 */
export function isProdEnv(environment: Environment): boolean {
  return environment === 'prod';
}
